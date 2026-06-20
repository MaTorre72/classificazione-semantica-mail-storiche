from __future__ import annotations

import queue
import os
import subprocess
import sys
import threading
from dataclasses import dataclass
from pathlib import Path
from tkinter import BooleanVar, StringVar, Tk, filedialog, messagebox, ttk
from tkinter.scrolledtext import ScrolledText


@dataclass(slots=True)
class CommandSpec:
    label: str
    args: list[str]


class EmailClusterGui:
    def __init__(self, root: Tk) -> None:
        self.root = root
        self.root.title("Email Semantic Cluster")
        self.root.geometry("980x680")
        self.output_queue: queue.Queue[str] = queue.Queue()
        self.running = False

        self.source_var = StringVar(value="mail")
        self.project_var = StringVar(value=os.environ.get("EMAIL_CLUSTER_PROJECT", "archivio_storico"))
        self.db_var = StringVar(value=os.environ.get("EMAIL_CLUSTER_DB", "data/email_cluster.sqlite"))
        self.config_var = StringVar(value="config/default.yaml")
        self.export_dir_var = StringVar(value="data/output")
        self.cluster_var = StringVar(value="0")
        self.label_var = StringVar(value="")
        self.session_var = StringVar(value="")
        self.query_var = StringVar(value="")
        self.skip_ml_var = BooleanVar(value=False)

        self._build_layout()
        self.root.after(100, self._drain_output_queue)

    def _build_layout(self) -> None:
        main = ttk.Frame(self.root, padding=12)
        main.pack(fill="both", expand=True)
        main.columnconfigure(0, weight=0)
        main.columnconfigure(1, weight=1)
        main.rowconfigure(4, weight=1)

        self._path_row(main, 0, "Sorgente", self.source_var, self._choose_source)
        self._entry_row(main, 1, "Progetto", self.project_var)
        self._path_row(main, 2, "Database", self.db_var, self._choose_db)
        self._path_row(main, 3, "Output", self.export_dir_var, self._choose_export_dir)

        notebook = ttk.Notebook(main)
        notebook.grid(row=4, column=0, columnspan=3, sticky="nsew", pady=(12, 8))

        pipeline_tab = ttk.Frame(notebook, padding=10)
        review_tab = ttk.Frame(notebook, padding=10)
        tools_tab = ttk.Frame(notebook, padding=10)
        notebook.add(pipeline_tab, text="Pipeline")
        notebook.add(review_tab, text="Cluster")
        notebook.add(tools_tab, text="Strumenti")

        self._build_pipeline_tab(pipeline_tab)
        self._build_review_tab(review_tab)
        self._build_tools_tab(tools_tab)

        log_frame = ttk.LabelFrame(main, text="Log", padding=8)
        log_frame.grid(row=5, column=0, columnspan=3, sticky="nsew")
        log_frame.rowconfigure(0, weight=1)
        log_frame.columnconfigure(0, weight=1)
        self.log = ScrolledText(log_frame, height=14, wrap="word")
        self.log.grid(row=0, column=0, sticky="nsew")

        footer = ttk.Frame(main)
        footer.grid(row=6, column=0, columnspan=3, sticky="ew", pady=(8, 0))
        self.status_label = ttk.Label(footer, text="Pronto")
        self.status_label.pack(side="left")
        ttk.Button(footer, text="Pulisci log", command=self._clear_log).pack(side="right")

    def _build_pipeline_tab(self, parent: ttk.Frame) -> None:
        parent.columnconfigure(0, weight=1)
        ttk.Checkbutton(parent, text="Salta ML", variable=self.skip_ml_var).grid(
            row=0, column=0, sticky="w", pady=(0, 8)
        )
        buttons = [
            ("Esegui V2", self._run_pipeline),
            ("Init DB", lambda: self._run_command("Init DB", ["init-db", "--db", self.db])),
            ("Import", self._run_import),
            ("Clean", self._run_clean),
            ("Embed", self._run_embed),
            ("Cluster", self._run_cluster),
            ("Report", self._run_report),
            ("Export CSV/JSON", self._run_exports),
            ("Status", self._run_status),
        ]
        self._button_grid(parent, buttons)

    def _build_review_tab(self, parent: ttk.Frame) -> None:
        parent.columnconfigure(1, weight=1)
        ttk.Label(parent, text="Sessione review").grid(row=0, column=0, sticky="w")
        ttk.Entry(parent, textvariable=self.session_var, width=12).grid(row=0, column=1, sticky="w")
        ttk.Button(parent, text="Avvia sessione", command=self._run_review_start).grid(row=0, column=2, padx=4)
        ttk.Button(parent, text="Dashboard", command=self._run_review_dashboard).grid(row=1, column=0, sticky="ew", padx=(0, 8), pady=4)
        ttk.Button(parent, text="Prossimo", command=self._run_review_next).grid(row=1, column=1, sticky="ew", pady=4)
        ttk.Button(parent, text="Apri cluster", command=self._run_review_cluster).grid(row=1, column=2, sticky="ew", pady=4)
        ttk.Button(parent, text="Lista cluster", command=self._run_clusters).grid(
            row=2, column=0, sticky="ew", padx=(0, 8), pady=4
        )
        ttk.Button(parent, text="Esporta revisione CSV", command=self._run_review_export).grid(
            row=2, column=1, sticky="ew", pady=4
        )

        ttk.Label(parent, text="Cluster ID").grid(row=3, column=0, sticky="w", pady=(12, 4))
        ttk.Entry(parent, textvariable=self.cluster_var, width=12).grid(
            row=3, column=1, sticky="w", pady=(12, 4)
        )
        ttk.Label(parent, text="Etichetta manuale").grid(row=4, column=0, sticky="w", pady=4)
        ttk.Entry(parent, textvariable=self.label_var).grid(row=4, column=1, sticky="ew", pady=4)
        ttk.Button(parent, text="Approva", command=self._run_approve_cluster).grid(row=5, column=0, sticky="ew", pady=4)
        ttk.Button(parent, text="Rinomina", command=self._run_rename_cluster).grid(row=5, column=1, sticky="ew", pady=4)
        ttk.Button(parent, text="Segna misto", command=self._run_mixed_cluster).grid(
            row=5, column=2, sticky="ew", pady=4
        )
        ttk.Button(parent, text="Crea label tassonomia", command=self._run_add_taxonomy).grid(
            row=6, column=1, sticky="ew", pady=4
        )
        ttk.Button(parent, text="Esporta report finale", command=self._run_final_report).grid(
            row=6, column=2, sticky="ew", pady=4
        )
        ttk.Button(parent, text="Proposte LLM cluster", command=self._run_llm_labels).grid(
            row=6, column=0, sticky="ew", pady=4
        )

    def _build_tools_tab(self, parent: ttk.Frame) -> None:
        parent.columnconfigure(1, weight=1)
        ttk.Label(parent, text="Ricerca").grid(row=0, column=0, sticky="w", padx=(0, 8))
        ttk.Entry(parent, textvariable=self.query_var).grid(row=0, column=1, sticky="ew")
        ttk.Button(parent, text="Cerca", command=self._run_search).grid(row=0, column=2, padx=(8, 0))
        ttk.Button(parent, text="Apri cartella output", command=self._open_output_dir).grid(
            row=1, column=1, sticky="e", pady=(12, 0)
        )

    def _button_grid(self, parent: ttk.Frame, buttons: list[tuple[str, object]]) -> None:
        for idx, (label, command) in enumerate(buttons):
            ttk.Button(parent, text=label, command=command).grid(
                row=1 + idx // 3, column=idx % 3, sticky="ew", padx=4, pady=4
            )
            parent.columnconfigure(idx % 3, weight=1)

    def _entry_row(self, parent: ttk.Frame, row: int, label: str, variable: StringVar) -> None:
        ttk.Label(parent, text=label).grid(row=row, column=0, sticky="w", pady=3)
        ttk.Entry(parent, textvariable=variable).grid(row=row, column=1, sticky="ew", padx=8, pady=3)

    def _path_row(
        self, parent: ttk.Frame, row: int, label: str, variable: StringVar, command: object
    ) -> None:
        self._entry_row(parent, row, label, variable)
        ttk.Button(parent, text="Sfoglia", command=command).grid(row=row, column=2, sticky="ew", pady=3)

    @property
    def source(self) -> str:
        return self.source_var.get().strip()

    @property
    def project(self) -> str:
        return self.project_var.get().strip()

    @property
    def db(self) -> str:
        return self.db_var.get().strip()

    @property
    def config(self) -> str:
        return self.config_var.get().strip()

    @property
    def export_dir(self) -> str:
        return self.export_dir_var.get().strip()

    def _choose_source(self) -> None:
        path = filedialog.askdirectory(title="Scegli cartella sorgente")
        if path:
            self.source_var.set(path)

    def _choose_db(self) -> None:
        path = filedialog.asksaveasfilename(
            title="Scegli database SQLite",
            defaultextension=".sqlite",
            filetypes=[("SQLite", "*.sqlite"), ("Tutti i file", "*.*")],
        )
        if path:
            self.db_var.set(path)

    def _choose_export_dir(self) -> None:
        path = filedialog.askdirectory(title="Scegli cartella output")
        if path:
            self.export_dir_var.set(path)

    def _run_pipeline(self) -> None:
        args = [
            "run",
            "--input",
            self.source,
            "--project",
            self.project,
            "--db",
            self.db,
            "--config",
            self.config,
        ]
        if self.skip_ml_var.get():
            args.append("--skip-ml")
        self._run_command("Run pipeline", args)

    def _run_import(self) -> None:
        self._run_command("Import", ["import", "--source", self.source, "--project", self.project, "--db", self.db])

    def _run_clean(self) -> None:
        self._run_command("Clean", ["clean", "--project", self.project, "--db", self.db, "--config", self.config])

    def _run_embed(self) -> None:
        self._run_command("Embed", ["embed", "--project", self.project, "--db", self.db, "--config", self.config])

    def _run_cluster(self) -> None:
        self._run_command("Cluster", ["cluster", "--project", self.project, "--db", self.db, "--config", self.config])

    def _run_report(self) -> None:
        self._run_command("Report", ["report", "--db", self.db, "--output", str(Path(self.export_dir) / "cluster_report.md")])

    def _run_exports(self) -> None:
        csv_args = ["export", "--format", "csv", "--output", str(Path(self.export_dir) / "emails.csv"), "--db", self.db]
        json_args = ["export", "--format", "json", "--output", str(Path(self.export_dir) / "emails.json"), "--db", self.db]
        self._run_command_sequence("Export", [CommandSpec("Export CSV", csv_args), CommandSpec("Export JSON", json_args)])

    def _run_status(self) -> None:
        self._run_command("Status", ["status", "--db", self.db])

    def _run_clusters(self) -> None:
        self._run_command("Clusters", ["clusters", "--db", self.db])

    def _run_review_export(self) -> None:
        self._run_command(
            "Review clusters",
            ["review-clusters", "--db", self.db, "--output", str(Path(self.export_dir) / "cluster_review.csv")],
        )

    def _review_args(self) -> tuple[str, str] | None:
        session = self.session_var.get().strip()
        cluster = self.cluster_var.get().strip()
        if not session:
            messagebox.showwarning("Sessione mancante", "Avvia o inserisci una sessione review.")
            return None
        return session, cluster

    def _run_review_start(self) -> None:
        self._run_command("Review start", ["review-start", "--project", self.project, "--run", "latest", "--db", self.db])

    def _run_review_dashboard(self) -> None:
        args = self._review_args()
        if args:
            self._run_command("Review dashboard", ["review-dashboard", "--session", args[0], "--db", self.db])

    def _run_review_next(self) -> None:
        args = self._review_args()
        if args:
            self._run_command("Review next", ["review-next", "--session", args[0], "--db", self.db])

    def _run_review_cluster(self) -> None:
        args = self._review_args()
        if args and args[1]:
            self._run_command("Review cluster", ["review-cluster", "--session", args[0], "--cluster", args[1], "--db", self.db])

    def _run_approve_cluster(self) -> None:
        args = self._review_args()
        if args and args[1]:
            self._run_command("Approve cluster", ["approve-cluster", "--session", args[0], "--cluster", args[1], "--db", self.db])

    def _run_rename_cluster(self) -> None:
        args = self._review_args()
        label = self.label_var.get().strip()
        if args and args[1] and label:
            self._run_command("Rename cluster", ["rename-cluster", "--session", args[0], "--cluster", args[1], "--label", label, "--db", self.db])

    def _run_mixed_cluster(self) -> None:
        args = self._review_args()
        if args and args[1]:
            self._run_command("Mixed cluster", ["mark-cluster-mixed", "--session", args[0], "--cluster", args[1], "--db", self.db])

    def _run_add_taxonomy(self) -> None:
        label = self.label_var.get().strip()
        if label:
            self._run_command("Add taxonomy", ["add-taxonomy-label", "--project", self.project, "--label", label, "--type", "tema_tecnico", "--db", self.db])

    def _run_final_report(self) -> None:
        args = self._review_args()
        if args:
            self._run_command("Final report", ["final-classification-report", "--session", args[0], "--output", str(Path(self.export_dir) / "final_report.html"), "--db", self.db])

    def _run_llm_labels(self) -> None:
        self._run_command("LLM cluster labels", ["llm-label-clusters", "--project", self.project, "--run", "latest", "--db", self.db, "--config", self.config])

    def _run_set_label(self) -> None:
        cluster_id = self.cluster_var.get().strip()
        label = self.label_var.get().strip()
        if not cluster_id or not label:
            messagebox.showwarning("Dati mancanti", "Inserisci cluster ID ed etichetta.")
            return
        self._run_command("Set label", ["set-label", cluster_id, label, "--db", self.db])

    def _run_search(self) -> None:
        query = self.query_var.get().strip()
        if not query:
            messagebox.showwarning("Ricerca vuota", "Inserisci un testo da cercare.")
            return
        self._run_command("Search", ["search", "--query", query, "--db", self.db])

    def _open_output_dir(self) -> None:
        path = Path(self.export_dir)
        path.mkdir(parents=True, exist_ok=True)
        subprocess.Popen(["explorer", str(path.resolve())])

    def _run_command(self, title: str, args: list[str]) -> None:
        self._run_command_sequence(title, [CommandSpec(title, args)])

    def _run_command_sequence(self, title: str, specs: list[CommandSpec]) -> None:
        if self.running:
            messagebox.showinfo("Comando in corso", "Attendi la fine del comando corrente.")
            return
        self.running = True
        self.status_label.config(text=f"In corso: {title}")
        thread = threading.Thread(target=self._worker, args=(specs,), daemon=True)
        thread.start()

    def _worker(self, specs: list[CommandSpec]) -> None:
        try:
            for spec in specs:
                command = [sys.executable, "-m", "email_cluster.cli.app", *spec.args]
                self.output_queue.put(f"\n$ {' '.join(command)}\n")
                process = subprocess.Popen(
                    command,
                    cwd=Path.cwd(),
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    text=True,
                    encoding="utf-8",
                    errors="replace",
                )
                assert process.stdout is not None
                for line in process.stdout:
                    self.output_queue.put(line)
                exit_code = process.wait()
                self.output_queue.put(f"[exit code: {exit_code}]\n")
                if exit_code != 0:
                    break
        finally:
            self.output_queue.put("__DONE__")

    def _drain_output_queue(self) -> None:
        while True:
            try:
                item = self.output_queue.get_nowait()
            except queue.Empty:
                break
            if item == "__DONE__":
                self.running = False
                self.status_label.config(text="Pronto")
            else:
                self.log.insert("end", item)
                self.log.see("end")
        self.root.after(100, self._drain_output_queue)

    def _clear_log(self) -> None:
        self.log.delete("1.0", "end")


def main() -> None:
    root = Tk()
    EmailClusterGui(root)
    root.mainloop()


if __name__ == "__main__":
    main()

import tkinter as tk
from tkinter import ttk, messagebox
import json

from mongodb_connection import test_mongo_connection, get_mongo_data
from postgres_connection import test_postgres_connection, get_postgres_data


class ConverterGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("Database Format Converter")
        self.root.geometry("1300x780")
        self.root.minsize(1200, 720)
        self.root.configure(bg="#edf2f7")

        self.current_source = tk.StringVar(value="PostgreSQL")
        self.current_target = tk.StringVar(value="PostgreSQL")

        self.source_entries = {}
        self.target_entries = {}
        self.current_documents = []

        self.setup_styles()
        self.build_ui()

    def setup_styles(self):
        style = ttk.Style()
        style.theme_use("clam")

        style.configure("Main.TFrame", background="#edf2f7")
        style.configure("Card.TFrame", background="#ffffff", relief="flat")

        style.configure(
            "Title.TLabel",
            background="#edf2f7",
            foreground="#0f172a",
            font=("Segoe UI", 26, "bold")
        )

        style.configure(
            "Subtitle.TLabel",
            background="#edf2f7",
            foreground="#475569",
            font=("Segoe UI", 11)
        )

        style.configure(
            "SectionTitle.TLabel",
            background="#ffffff",
            foreground="#0f172a",
            font=("Segoe UI", 15, "bold")
        )

        style.configure(
            "FieldLabel.TLabel",
            background="#ffffff",
            foreground="#334155",
            font=("Segoe UI", 10)
        )

        style.configure(
            "Primary.TButton",
            font=("Segoe UI", 10, "bold"),
            padding=10
        )

        style.map(
            "Primary.TButton",
            background=[("active", "#1d4ed8"), ("!disabled", "#2563eb")],
            foreground=[("!disabled", "white")]
        )

        style.configure(
            "Success.TButton",
            font=("Segoe UI", 10, "bold"),
            padding=10
        )

        style.map(
            "Success.TButton",
            background=[("active", "#15803d"), ("!disabled", "#16a34a")],
            foreground=[("!disabled", "white")]
        )

        style.configure(
            "Secondary.TButton",
            font=("Segoe UI", 10),
            padding=8
        )

        style.map(
            "Secondary.TButton",
            background=[("active", "#cbd5e1"), ("!disabled", "#e2e8f0")],
            foreground=[("!disabled", "#0f172a")]
        )

        style.configure("TCombobox", padding=6)

    def build_ui(self):
        main = ttk.Frame(self.root, style="Main.TFrame", padding=20)
        main.pack(fill="both", expand=True)

        header = ttk.Frame(main, style="Main.TFrame")
        header.pack(fill="x", pady=(0, 18))

        ttk.Label(
            header,
            text="Database Format Converter",
            style="Title.TLabel"
        ).pack(anchor="center")

        ttk.Label(
            header,
            text="PostgreSQL • MongoDB • Neo4j",
            style="Subtitle.TLabel"
        ).pack(anchor="center", pady=(6, 0))

        content = ttk.Frame(main, style="Main.TFrame")
        content.pack(fill="both", expand=True)

        self.build_scrollable_left_panel(content)

        right_panel = ttk.Frame(content, style="Card.TFrame", padding=20)
        right_panel.pack(side="left", fill="both", expand=True)

        self.build_right_panel(right_panel)

    def build_scrollable_left_panel(self, parent):
        outer_left = ttk.Frame(parent, style="Card.TFrame")
        outer_left.pack(side="left", fill="y", padx=(0, 16))

        canvas = tk.Canvas(
            outer_left,
            bg="#ffffff",
            highlightthickness=0,
            width=330
        )
        canvas.pack(side="left", fill="y", expand=False)

        scrollbar = ttk.Scrollbar(
            outer_left,
            orient="vertical",
            command=canvas.yview
        )
        scrollbar.pack(side="right", fill="y")

        canvas.configure(yscrollcommand=scrollbar.set)

        left_panel = ttk.Frame(canvas, style="Card.TFrame", padding=20)
        canvas_window = canvas.create_window((0, 0), window=left_panel, anchor="nw")

        def update_scrollregion(event=None):
            canvas.configure(scrollregion=canvas.bbox("all"))

        def resize_inner_frame(event):
            canvas.itemconfig(canvas_window, width=event.width)

        left_panel.bind("<Configure>", update_scrollregion)
        canvas.bind("<Configure>", resize_inner_frame)

        def on_mousewheel(event):
            canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")

        def bind_mousewheel(_event):
            canvas.bind_all("<MouseWheel>", on_mousewheel)

        def unbind_mousewheel(_event):
            canvas.unbind_all("<MouseWheel>")

        canvas.bind("<Enter>", bind_mousewheel)
        canvas.bind("<Leave>", unbind_mousewheel)

        self.build_left_panel(left_panel)

    def build_left_panel(self, parent):
        ttk.Label(
            parent,
            text="Konfiguracja konwersji",
            style="SectionTitle.TLabel"
        ).pack(anchor="w", pady=(0, 15))

        ttk.Label(parent, text="Model źródłowy", style="FieldLabel.TLabel").pack(anchor="w")
        source_combo = ttk.Combobox(
            parent,
            textvariable=self.current_source,
            values=["PostgreSQL", "MongoDB", "Neo4j"],
            state="readonly",
            width=28
        )
        source_combo.pack(fill="x", pady=(6, 12))
        source_combo.bind("<<ComboboxSelected>>", lambda e: self.refresh_forms())

        ttk.Label(parent, text="Model docelowy", style="FieldLabel.TLabel").pack(anchor="w")
        target_combo = ttk.Combobox(
            parent,
            textvariable=self.current_target,
            values=["PostgreSQL", "MongoDB", "Neo4j"],
            state="readonly",
            width=28
        )
        target_combo.pack(fill="x", pady=(6, 18))
        target_combo.bind("<<ComboboxSelected>>", lambda e: self.refresh_forms())

        self.source_card = tk.Frame(parent, bg="#f8fafc", bd=1, relief="solid")
        self.source_card.pack(fill="x", pady=(0, 14))

        self.target_card = tk.Frame(parent, bg="#f8fafc", bd=1, relief="solid")
        self.target_card.pack(fill="x", pady=(0, 18))

        button_frame = tk.Frame(parent, bg="#ffffff")
        button_frame.pack(fill="x", pady=(10, 0))

        ttk.Button(
            button_frame,
            text="Test połączenia",
            style="Primary.TButton",
            command=self.test_source
        ).pack(fill="x", pady=(0, 10))

        ttk.Button(
            button_frame,
            text="Konwertuj",
            style="Success.TButton",
            command=self.convert_data
        ).pack(fill="x", pady=(0, 10))

        ttk.Button(
            button_frame,
            text="Wyczyść log",
            style="Secondary.TButton",
            command=self.clear_log
        ).pack(fill="x")

        self.refresh_forms()

    def build_right_panel(self, parent):
        ttk.Label(
            parent,
            text="Log operacji",
            style="SectionTitle.TLabel"
        ).pack(anchor="w", pady=(0, 10))

        log_container = tk.Frame(parent, bg="#0b132b", bd=1, relief="solid")
        log_container.pack(fill="x", pady=(0, 16))

        self.log_text = tk.Text(
            log_container,
            height=10,
            bg="#0b132b",
            fg="#e2e8f0",
            insertbackground="white",
            relief="flat",
            wrap="word",
            font=("Consolas", 10),
            padx=12,
            pady=12
        )
        self.log_text.pack(fill="x", expand=False)

        ttk.Label(
            parent,
            text="Dane z PostgreSQL",
            style="SectionTitle.TLabel"
        ).pack(anchor="w", pady=(0, 10))

        table_container = tk.Frame(parent, bg="#ffffff", bd=1, relief="solid")
        table_container.pack(fill="both", expand=True, pady=(0, 16))

        columns = ("id", "document")
        self.documents_tree = ttk.Treeview(
            table_container,
            columns=columns,
            show="headings",
            height=10
        )
        self.documents_tree.heading("id", text="ID / klucz")
        self.documents_tree.heading("document", text="Podgląd rekordu")

        self.documents_tree.column("id", width=180, anchor="w")
        self.documents_tree.column("document", width=700, anchor="w")

        tree_scroll_y = ttk.Scrollbar(table_container, orient="vertical", command=self.documents_tree.yview)
        tree_scroll_x = ttk.Scrollbar(table_container, orient="horizontal", command=self.documents_tree.xview)

        self.documents_tree.configure(yscrollcommand=tree_scroll_y.set, xscrollcommand=tree_scroll_x.set)

        self.documents_tree.pack(side="left", fill="both", expand=True)
        tree_scroll_y.pack(side="right", fill="y")
        tree_scroll_x.pack(side="bottom", fill="x")

        self.documents_tree.bind("<<TreeviewSelect>>", self.show_selected_document)

        ttk.Label(
            parent,
            text="Szczegóły wybranego rekordu",
            style="SectionTitle.TLabel"
        ).pack(anchor="w", pady=(0, 10))

        details_container = tk.Frame(parent, bg="#111827", bd=1, relief="solid")
        details_container.pack(fill="both", expand=True)

        self.document_details = tk.Text(
            details_container,
            bg="#111827",
            fg="#f8fafc",
            insertbackground="white",
            relief="flat",
            wrap="word",
            font=("Consolas", 10),
            padx=12,
            pady=12
        )
        self.document_details.pack(fill="both", expand=True)

        self.log("Aplikacja uruchomiona.")

    def refresh_forms(self):
        for widget in self.source_card.winfo_children():
            widget.destroy()
        for widget in self.target_card.winfo_children():
            widget.destroy()

        self.source_entries = self.build_form(self.source_card, self.current_source.get(), "Źródło")
        self.target_entries = self.build_form(self.target_card, self.current_target.get(), "Cel")

    def build_form(self, parent, model_name, section_name):
        container = tk.Frame(parent, bg="#f8fafc")
        container.pack(fill="both", expand=True, padx=14, pady=14)

        tk.Label(
            container,
            text=f"{section_name}: {model_name}",
            bg="#f8fafc",
            fg="#0f172a",
            font=("Segoe UI", 12, "bold")
        ).pack(anchor="w", pady=(0, 10))

        fields = self.get_fields_for_model(model_name)
        entries = {}

        form = tk.Frame(container, bg="#f8fafc")
        form.pack(fill="x")

        for i, field in enumerate(fields):
            tk.Label(
                form,
                text=field,
                bg="#f8fafc",
                fg="#334155",
                font=("Segoe UI", 10)
            ).grid(row=i, column=0, sticky="w", pady=6, padx=(0, 10))

            entry = tk.Entry(
                form,
                width=28,
                relief="flat",
                bd=0,
                bg="white",
                fg="#0f172a",
                insertbackground="#0f172a",
                font=("Segoe UI", 10),
                show="*" if field == "password" else ""
            )
            entry.grid(row=i, column=1, sticky="ew", pady=6)

            if field == "host":
                entry.insert(0, "localhost")
            elif field == "port":
                if model_name == "PostgreSQL":
                    entry.insert(0, "5432")
                elif model_name == "MongoDB":
                    entry.insert(0, "27017")
                elif model_name == "Neo4j":
                    entry.insert(0, "7687")
            elif field == "database":
                if model_name == "MongoDB":
                    entry.insert(0, "db_converter")
                entry.insert(0, "db_converter")
            elif field == "user":
                entry.insert(0, "postgres")
            elif field == "table":
                entry.insert(0, "users")

            entries[field] = entry

        form.grid_columnconfigure(1, weight=1)
        return entries

    def get_fields_for_model(self, model_name):
        if model_name == "PostgreSQL":
            return ["host", "port", "database", "user", "password", "table"]
        elif model_name == "MongoDB":
            return ["host", "port", "database"]
        elif model_name == "Neo4j":
            return ["host", "port", "user", "password"]
        return []

    def get_form_data(self, entries):
        data = {}
        for key, entry in entries.items():
            data[key] = entry.get().strip()
        return data

    def validate_data(self, data):
        for key, value in data.items():
            if not value:
                return False, f"Pole '{key}' nie może być puste."
        return True, ""

    def display_records(self, records, id_field=None):
        self.current_documents = records

        for item in self.documents_tree.get_children():
            self.documents_tree.delete(item)

        self.document_details.delete("1.0", tk.END)

        for index, record in enumerate(records):
            record_id = "brak id"

            if id_field and id_field in record:
                record_id = record[id_field]
            elif "_id" in record:
                record_id = record["_id"]
            elif "id" in record:
                record_id = record["id"]

            preview_text = json.dumps(record, ensure_ascii=False, default=str)

            if len(preview_text) > 120:
                preview_text = preview_text[:120] + "..."

            self.documents_tree.insert("", "end", iid=str(index), values=(record_id, preview_text))

    def show_selected_document(self, event=None):
        selected = self.documents_tree.selection()
        if not selected:
            return

        item_id = selected[0]
        index = int(item_id)

        if index < 0 or index >= len(self.current_documents):
            return

        document = self.current_documents[index]

        self.document_details.delete("1.0", tk.END)
        formatted = json.dumps(document, indent=4, ensure_ascii=False, default=str)
        self.document_details.insert(tk.END, formatted)

    def test_source(self):
        model = self.current_source.get()
        data = self.get_form_data(self.source_entries)
        valid, message = self.validate_data(data)

        if not valid:
            messagebox.showwarning("Brak danych", message)
            return

        if model == "PostgreSQL":
            try:
                result = test_postgres_connection(
                    data["host"],
                    data["port"],
                    data["database"],
                    data["user"],
                    data["password"]
                )

                if not result:
                    self.log("Nie udało się połączyć z PostgreSQL.")
                    messagebox.showerror("Błąd", "Nie udało się połączyć z PostgreSQL.")
                    return

                postgres_data = get_postgres_data(
                    data["host"],
                    data["port"],
                    data["database"],
                    data["user"],
                    data["password"],
                    data["table"]
                )

                self.display_records(postgres_data, id_field="id")

                self.log(f"Połączenie z PostgreSQL działa poprawnie. Liczba rekordów: {len(postgres_data)}")
                messagebox.showinfo(
                    "Sukces",
                    f"Połączenie z PostgreSQL działa poprawnie.\nPobrano {len(postgres_data)} rekordów."
                )

            except Exception as e:
                self.log(f"Błąd podczas testu połączenia z PostgreSQL: {str(e)}")
                messagebox.showerror("Błąd", str(e))
            return

        self.log(f"Test połączenia dla {model} nie jest jeszcze dostępny.")
        messagebox.showinfo(
            "Informacja",
            f"Test połączenia dla {model} nie jest jeszcze dostępny."
        )

    def convert_data(self):
        source_model = self.current_source.get()
        target_model = self.current_target.get()

        if source_model == target_model:
            messagebox.showwarning(
                "Błąd konfiguracji",
                "Model źródłowy i docelowy nie mogą być takie same."
            )
            return

        source_data = self.get_form_data(self.source_entries)
        target_data = self.get_form_data(self.target_entries)

        source_valid, source_message = self.validate_data(source_data)
        if not source_valid:
            messagebox.showwarning("Brak danych źródła", source_message)
            return

        target_valid, target_message = self.validate_data(target_data)
        if not target_valid:
            messagebox.showwarning("Brak danych celu", target_message)
            return

        self.log(f"Wybrano konwersję: {source_model} -> {target_model}")

        if source_model == "PostgreSQL":
            try:
                postgres_data = get_postgres_data(
                    source_data["host"],
                    source_data["port"],
                    source_data["database"],
                    source_data["user"],
                    source_data["password"],
                    source_data["table"]
                )

                self.display_records(postgres_data, id_field="id")

                self.log(f"Pobrano {len(postgres_data)} rekordów z PostgreSQL.")
                messagebox.showinfo(
                    "Sukces",
                    f"Odczytano {len(postgres_data)} rekordów z PostgreSQL."
                )

            except Exception as e:
                self.log(f"Błąd podczas odczytu danych z PostgreSQL: {str(e)}")
                messagebox.showerror("Błąd", str(e))
            return

        messagebox.showinfo(
            "Informacja",
            f"Konwersja {source_model} -> {target_model} nie jest jeszcze zaimplementowana."
        )

    def clear_log(self):
        self.log_text.delete("1.0", tk.END)
        for item in self.documents_tree.get_children():
            self.documents_tree.delete(item)
        self.document_details.delete("1.0", tk.END)
        self.current_documents = []
        self.log("Log wyczyszczony.")

    def log(self, message):
        self.log_text.insert(tk.END, message + "\n")
        self.log_text.see(tk.END)


if __name__ == "__main__":
    root = tk.Tk()
    app = ConverterGUI(root)
    root.mainloop()
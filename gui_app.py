import tkinter as tk
from tkinter import ttk, messagebox
import json

from mongodb_connection import test_mongo_connection, get_mongo_data, get_mongo_collections
from postgres_connection import test_postgres_connection, get_postgres_tables
from converter_service import convert_database


class ScrollableFrame(ttk.Frame):
    def __init__(self, parent, bg="#edf2f7", width=None, height=None):
        super().__init__(parent)

        self.canvas = tk.Canvas(
            self,
            borderwidth=0,
            highlightthickness=0,
            bg=bg
        )

        self.scrollbar = ttk.Scrollbar(
            self,
            orient="vertical",
            command=self.canvas.yview
        )

        self.scrollable_frame = ttk.Frame(
            self.canvas,
            style="Main.TFrame"
        )

        self.window_id = self.canvas.create_window(
            (0, 0),
            window=self.scrollable_frame,
            anchor="nw"
        )

        self.canvas.configure(yscrollcommand=self.scrollbar.set)

        if width is not None:
            self.canvas.configure(width=width)

        if height is not None:
            self.canvas.configure(height=height)

        self.canvas.pack(side="left", fill="both", expand=True)
        self.scrollbar.pack(side="right", fill="y")

        self.scrollable_frame.bind(
            "<Configure>",
            self._on_frame_configure
        )

        self.canvas.bind(
            "<Configure>",
            self._on_canvas_configure
        )

        self.canvas.bind("<Enter>", self._bind_mousewheel)
        self.canvas.bind("<Leave>", self._unbind_mousewheel)

    def _on_frame_configure(self, event=None):
        self.canvas.configure(
            scrollregion=self.canvas.bbox("all")
        )

    def _on_canvas_configure(self, event):
        self.canvas.itemconfig(
            self.window_id,
            width=event.width
        )

    def _bind_mousewheel(self, event=None):
        self.canvas.bind_all("<MouseWheel>", self._on_mousewheel)
        self.canvas.bind_all("<Button-4>", self._on_mousewheel_linux)
        self.canvas.bind_all("<Button-5>", self._on_mousewheel_linux)

    def _unbind_mousewheel(self, event=None):
        self.canvas.unbind_all("<MouseWheel>")
        self.canvas.unbind_all("<Button-4>")
        self.canvas.unbind_all("<Button-5>")

    def _on_mousewheel(self, event):
        self.canvas.yview_scroll(
            int(-1 * (event.delta / 120)),
            "units"
        )

    def _on_mousewheel_linux(self, event):
        if event.num == 4:
            self.canvas.yview_scroll(-1, "units")
        elif event.num == 5:
            self.canvas.yview_scroll(1, "units")


class ConverterGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("Database Format Converter")
        self.root.geometry("1200x750")
        self.root.minsize(900, 600)
        self.root.configure(bg="#edf2f7")

        self.current_source = tk.StringVar(value="MongoDB")
        self.current_target = tk.StringVar(value="PostgreSQL")
        self.mongo_write_mode = tk.StringVar(value="Embedding")

        self.empty_object_option = "Wybierz..."
        self.all_objects_option = "Wszystkie"
        self.selected_object = tk.StringVar(value=self.empty_object_option)

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
            padding=8
        )

        style.map(
            "Primary.TButton",
            background=[("active", "#1d4ed8"), ("!disabled", "#2563eb")],
            foreground=[("!disabled", "white")]
        )

        style.configure(
            "Success.TButton",
            font=("Segoe UI", 10, "bold"),
            padding=8
        )

        style.map(
            "Success.TButton",
            background=[("active", "#15803d"), ("!disabled", "#16a34a")],
            foreground=[("!disabled", "white")]
        )

        style.configure(
            "Secondary.TButton",
            font=("Segoe UI", 10),
            padding=6
        )

        style.map(
            "Secondary.TButton",
            background=[("active", "#cbd5e1"), ("!disabled", "#e2e8f0")],
            foreground=[("!disabled", "#0f172a")]
        )

        style.configure("TCombobox", padding=4)

    def build_ui(self):
        main = ttk.Frame(self.root, style="Main.TFrame", padding=16)
        main.pack(fill="both", expand=True)

        header = ttk.Frame(main, style="Main.TFrame")
        header.pack(fill="x", pady=(0, 12))

        ttk.Label(
            header,
            text="Database Format Converter",
            style="Title.TLabel"
        ).pack(anchor="center")

        ttk.Label(
            header,
            text="PostgreSQL • MongoDB",
            style="Subtitle.TLabel"
        ).pack(anchor="center", pady=(4, 0))

        content = ttk.Frame(main, style="Main.TFrame")
        content.pack(fill="both", expand=True)

        left_scroll = ScrollableFrame(
            content,
            bg="#edf2f7",
            width=360
        )
        left_scroll.pack(side="left", fill="both", padx=(0, 12))

        right_scroll = ScrollableFrame(
            content,
            bg="#edf2f7"
        )
        right_scroll.pack(side="left", fill="both", expand=True)

        left_panel = ttk.Frame(
            left_scroll.scrollable_frame,
            style="Card.TFrame",
            padding=14
        )
        left_panel.pack(fill="both", expand=True)

        right_panel = ttk.Frame(
            right_scroll.scrollable_frame,
            style="Card.TFrame",
            padding=16
        )
        right_panel.pack(fill="both", expand=True)

        self.build_left_panel(left_panel)
        self.build_right_panel(right_panel)

    def build_left_panel(self, parent):
        ttk.Label(
            parent,
            text="Konfiguracja konwersji",
            style="SectionTitle.TLabel"
        ).pack(anchor="w", pady=(0, 10))

        ttk.Label(
            parent,
            text="Model źródłowy",
            style="FieldLabel.TLabel"
        ).pack(anchor="w")

        source_combo = ttk.Combobox(
            parent,
            textvariable=self.current_source,
            values=["PostgreSQL", "MongoDB"],
            state="readonly",
            width=28
        )
        source_combo.pack(fill="x", pady=(4, 8))
        source_combo.bind("<<ComboboxSelected>>", lambda e: self.refresh_forms())

        ttk.Label(
            parent,
            text="Model docelowy",
            style="FieldLabel.TLabel"
        ).pack(anchor="w")

        target_combo = ttk.Combobox(
            parent,
            textvariable=self.current_target,
            values=["PostgreSQL", "MongoDB"],
            state="readonly",
            width=28
        )
        target_combo.pack(fill="x", pady=(4, 10))
        target_combo.bind("<<ComboboxSelected>>", lambda e: self.refresh_forms())

        self.source_card = tk.Frame(parent, bg="#f8fafc", bd=1, relief="solid")
        self.source_card.pack(fill="x", pady=(0, 8))

        self.target_card = tk.Frame(parent, bg="#f8fafc", bd=1, relief="solid")
        self.target_card.pack(fill="x", pady=(0, 8))

        self.object_card = tk.Frame(parent, bg="#f8fafc", bd=1, relief="solid")
        self.object_card.pack(fill="x", pady=(0, 10))

        self.build_object_selector(self.object_card)

        self.mode_card = tk.Frame(parent, bg="#f8fafc", bd=1, relief="solid")
        self.mode_card.pack(fill="x", pady=(0, 10))

        self.build_mongo_mode_selector(self.mode_card)

        button_frame = tk.Frame(parent, bg="#ffffff")
        button_frame.pack(fill="x", pady=(0, 0))

        ttk.Button(
            button_frame,
            text="Test połączenia",
            style="Primary.TButton",
            command=self.test_source
        ).pack(fill="x", pady=(0, 6))

        ttk.Button(
            button_frame,
            text="Konwertuj",
            style="Success.TButton",
            command=self.convert_data
        ).pack(fill="x", pady=(0, 6))

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
        ).pack(anchor="w", pady=(0, 8))

        log_container = tk.Frame(parent, bg="#0b132b", bd=1, relief="solid")
        log_container.pack(fill="x", pady=(0, 12))

        self.log_text = tk.Text(
            log_container,
            height=8,
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

        self.preview_label = ttk.Label(
            parent,
            text=f"Podgląd danych: {self.current_source.get()}",
            style="SectionTitle.TLabel"
        )
        self.preview_label.pack(anchor="w", pady=(0, 8))

        table_container = tk.Frame(parent, bg="#ffffff", bd=1, relief="solid")
        table_container.pack(fill="both", expand=True, pady=(0, 12))

        columns = ("id", "document")

        self.documents_tree = ttk.Treeview(
            table_container,
            columns=columns,
            show="headings",
            height=10
        )

        self.documents_tree.heading("id", text="Identyfikator")
        self.documents_tree.heading("document", text="Podgląd rekordu/dokumentu")

        self.documents_tree.column("id", width=220, anchor="w")
        self.documents_tree.column("document", width=850, anchor="w")

        tree_scroll_y = ttk.Scrollbar(
            table_container,
            orient="vertical",
            command=self.documents_tree.yview
        )

        tree_scroll_x = ttk.Scrollbar(
            table_container,
            orient="horizontal",
            command=self.documents_tree.xview
        )

        self.documents_tree.configure(
            yscrollcommand=tree_scroll_y.set,
            xscrollcommand=tree_scroll_x.set
        )

        self.documents_tree.grid(row=0, column=0, sticky="nsew")
        tree_scroll_y.grid(row=0, column=1, sticky="ns")
        tree_scroll_x.grid(row=1, column=0, sticky="ew")

        table_container.grid_rowconfigure(0, weight=1)
        table_container.grid_columnconfigure(0, weight=1)

        self.documents_tree.bind("<<TreeviewSelect>>", self.show_selected_document)

        ttk.Label(
            parent,
            text="Szczegóły wybranego rekordu/dokumentu",
            style="SectionTitle.TLabel"
        ).pack(anchor="w", pady=(0, 8))

        details_container = tk.Frame(parent, bg="#111827", bd=1, relief="solid")
        details_container.pack(fill="both", expand=True)

        self.document_details = tk.Text(
            details_container,
            height=18,
            bg="#111827",
            fg="#f8fafc",
            insertbackground="white",
            relief="flat",
            wrap="none",
            font=("Consolas", 10),
            padx=12,
            pady=12
        )

        details_scroll_y = ttk.Scrollbar(
            details_container,
            orient="vertical",
            command=self.document_details.yview
        )

        details_scroll_x = ttk.Scrollbar(
            details_container,
            orient="horizontal",
            command=self.document_details.xview
        )

        self.document_details.configure(
            yscrollcommand=details_scroll_y.set,
            xscrollcommand=details_scroll_x.set
        )

        self.document_details.grid(row=0, column=0, sticky="nsew")
        details_scroll_y.grid(row=0, column=1, sticky="ns")
        details_scroll_x.grid(row=1, column=0, sticky="ew")

        details_container.grid_rowconfigure(0, weight=1)
        details_container.grid_columnconfigure(0, weight=1)

        self.log("Aplikacja uruchomiona.")

    def build_object_selector(self, parent):
        container = tk.Frame(parent, bg="#f8fafc")
        container.pack(fill="both", expand=True, padx=10, pady=10)

        tk.Label(
            container,
            text="Zakres konwersji",
            bg="#f8fafc",
            fg="#0f172a",
            font=("Segoe UI", 11, "bold")
        ).pack(anchor="w", pady=(0, 6))

        tk.Label(
            container,
            text="Tabela/kolekcja źródłowa",
            bg="#f8fafc",
            fg="#334155",
            font=("Segoe UI", 9)
        ).pack(anchor="w", pady=(0, 4))

        self.object_combo = ttk.Combobox(
            container,
            textvariable=self.selected_object,
            values=[self.empty_object_option],
            state="readonly",
            width=28
        )
        self.object_combo.pack(fill="x", pady=(0, 6))

        ttk.Button(
            container,
            text="Pobierz tabele/kolekcje",
            style="Secondary.TButton",
            command=self.load_source_objects
        ).pack(fill="x")

    def build_mongo_mode_selector(self, parent):
        container = tk.Frame(parent, bg="#f8fafc")
        container.pack(fill="both", expand=True, padx=10, pady=10)

        tk.Label(
            container,
            text="Tryb zapisu do MongoDB",
            bg="#f8fafc",
            fg="#0f172a",
            font=("Segoe UI", 11, "bold")
        ).pack(anchor="w", pady=(0, 6))

        tk.Label(
            container,
            text="Dotyczy konwersji PostgreSQL → MongoDB",
            bg="#f8fafc",
            fg="#334155",
            font=("Segoe UI", 9)
        ).pack(anchor="w", pady=(0, 4))

        self.mode_combo = ttk.Combobox(
            container,
            textvariable=self.mongo_write_mode,
            values=["Embedding", "Referencing"],
            state="readonly",
            width=28
        )
        self.mode_combo.pack(fill="x", pady=(0, 6))

    def load_source_objects(self):
        source_model = self.current_source.get()
        source_data = self.get_form_data(self.source_entries)

        valid, message = self.validate_data(source_data)

        if not valid:
            messagebox.showwarning("Brak danych źródła", message)
            return

        try:
            if source_model == "MongoDB":
                objects = get_mongo_collections(
                    source_data["host"],
                    source_data["port"],
                    source_data["database"]
                )

            elif source_model == "PostgreSQL":
                objects = get_postgres_tables(
                    source_data["host"],
                    source_data["port"],
                    source_data["database"],
                    source_data["user"],
                    source_data["password"]
                )

            else:
                messagebox.showinfo(
                    "Informacja",
                    f"Pobieranie tabel/kolekcji dla {source_model} nie jest dostępne."
                )
                return

            if not objects:
                self.object_combo["values"] = [self.empty_object_option]
                self.selected_object.set(self.empty_object_option)

                self.log(f"Nie znaleziono tabel/kolekcji dla {source_model}.")
                messagebox.showinfo(
                    "Brak danych",
                    "Nie znaleziono żadnych tabel/kolekcji w wybranej bazie."
                )
                return

            values = [self.empty_object_option] + objects + [self.all_objects_option]

            self.object_combo["values"] = values
            self.selected_object.set(self.empty_object_option)

            self.log(
                f"Pobrano obiekty źródłowe dla {source_model}: {', '.join(objects)}"
            )
            self.log("Lista została załadowana. Wybierz obiekt z pola wyboru.")

        except Exception as e:
            self.log(f"Błąd podczas pobierania tabel/kolekcji: {str(e)}")
            messagebox.showerror("Błąd", str(e))

    def refresh_forms(self):
        for widget in self.source_card.winfo_children():
            widget.destroy()

        for widget in self.target_card.winfo_children():
            widget.destroy()

        self.source_entries = self.build_form(
            self.source_card,
            self.current_source.get(),
            "Źródło"
        )

        self.target_entries = self.build_form(
            self.target_card,
            self.current_target.get(),
            "Cel"
        )

        if hasattr(self, "object_combo"):
            self.object_combo["values"] = [self.empty_object_option]
            self.selected_object.set(self.empty_object_option)

        if hasattr(self, "preview_label"):
            self.preview_label.config(
                text=f"Podgląd danych: {self.current_source.get()}"
            )

        self.update_mode_selector_state()
        self.clear_preview()

    def update_mode_selector_state(self):
        if not hasattr(self, "mode_combo"):
            return

        source_model = self.current_source.get()
        target_model = self.current_target.get()

        if source_model == "PostgreSQL" and target_model == "MongoDB":
            self.mode_combo.configure(state="readonly")
        else:
            self.mode_combo.configure(state="disabled")

    def build_form(self, parent, model_name, section_name):
        container = tk.Frame(parent, bg="#f8fafc")
        container.pack(fill="both", expand=True, padx=10, pady=10)

        tk.Label(
            container,
            text=f"{section_name}: {model_name}",
            bg="#f8fafc",
            fg="#0f172a",
            font=("Segoe UI", 11, "bold")
        ).pack(anchor="w", pady=(0, 8))

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
                font=("Segoe UI", 9)
            ).grid(row=i, column=0, sticky="w", pady=4, padx=(0, 10))

            entry = tk.Entry(
                form,
                width=26,
                relief="flat",
                bd=0,
                bg="white",
                fg="#0f172a",
                insertbackground="#0f172a",
                font=("Segoe UI", 9),
                show="*" if field == "password" else ""
            )
            entry.grid(row=i, column=1, sticky="ew", pady=4)

            if field == "host":
                entry.insert(0, "localhost")

            elif field == "port":
                if model_name == "PostgreSQL":
                    entry.insert(0, "5432")
                elif model_name == "MongoDB":
                    entry.insert(0, "27017")

            elif field == "database":
                entry.insert(0, "db_converter")

            elif field == "user":
                if model_name == "PostgreSQL":
                    entry.insert(0, "postgres")

            entries[field] = entry

        form.grid_columnconfigure(1, weight=1)

        return entries

    def get_fields_for_model(self, model_name):
        if model_name == "PostgreSQL":
            return ["host", "port", "database", "user", "password"]

        if model_name == "MongoDB":
            return ["host", "port", "database"]

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

    def clear_preview(self):
        if hasattr(self, "documents_tree"):
            for item in self.documents_tree.get_children():
                self.documents_tree.delete(item)

        if hasattr(self, "document_details"):
            self.document_details.delete("1.0", tk.END)

        self.current_documents = []

    def display_mongo_documents(self, documents):
        self.current_documents = documents

        for item in self.documents_tree.get_children():
            self.documents_tree.delete(item)

        self.document_details.delete("1.0", tk.END)

        for index, doc in enumerate(documents):
            doc_id = doc.get("_id", doc.get("id", "brak id"))

            preview_doc = dict(doc)
            preview_text = json.dumps(preview_doc, ensure_ascii=False)

            if len(preview_text) > 120:
                preview_text = preview_text[:120] + "..."

            self.documents_tree.insert(
                "",
                "end",
                iid=str(index),
                values=(doc_id, preview_text)
            )

    def display_intermediate_data(self, intermediate_data):
        self.current_documents = []

        for item in self.documents_tree.get_children():
            self.documents_tree.delete(item)

        self.document_details.delete("1.0", tk.END)

        index = 0

        for object_name, records in intermediate_data.items():
            if object_name.startswith("__"):
                continue

            for record in records:
                row = dict(record)
                row["_source_object"] = object_name

                self.current_documents.append(row)

                record_id = row.get("_id", row.get("id", row.get("user_id", "brak id")))

                preview_text = json.dumps(row, ensure_ascii=False)

                if len(preview_text) > 120:
                    preview_text = preview_text[:120] + "..."

                self.documents_tree.insert(
                    "",
                    "end",
                    iid=str(index),
                    values=(record_id, preview_text)
                )

                index += 1

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

        formatted = json.dumps(
            document,
            indent=4,
            ensure_ascii=False
        )

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

                if result:
                    self.log("Połączenie z PostgreSQL działa poprawnie.")
                    messagebox.showinfo(
                        "Sukces",
                        "Połączenie z PostgreSQL działa poprawnie."
                    )
                else:
                    self.log("Nie udało się połączyć z PostgreSQL.")
                    messagebox.showerror(
                        "Błąd",
                        "Nie udało się połączyć z PostgreSQL."
                    )

            except Exception as e:
                self.log(f"Błąd podczas testu połączenia z PostgreSQL: {str(e)}")
                messagebox.showerror("Błąd", str(e))

            return

        if model == "MongoDB":
            try:
                result = test_mongo_connection(
                    data["host"],
                    data["port"],
                    data["database"]
                )

                if not result:
                    self.log("Nie udało się połączyć z MongoDB.")
                    messagebox.showerror(
                        "Błąd",
                        "Nie udało się połączyć z MongoDB."
                    )
                    return

                selected_object = self.selected_object.get()

                if selected_object == self.empty_object_option or selected_object == "":
                    collections = get_mongo_collections(
                        data["host"],
                        data["port"],
                        data["database"]
                    )

                    if not collections:
                        self.log("MongoDB działa, ale nie znaleziono kolekcji.")
                        messagebox.showinfo(
                            "Sukces",
                            "Połączenie z MongoDB działa poprawnie, ale baza nie zawiera kolekcji."
                        )
                        return

                    collection_name = collections[0]

                elif selected_object == self.all_objects_option:
                    collections = get_mongo_collections(
                        data["host"],
                        data["port"],
                        data["database"]
                    )

                    if not collections:
                        self.log("MongoDB działa, ale nie znaleziono kolekcji.")
                        messagebox.showinfo(
                            "Sukces",
                            "Połączenie z MongoDB działa poprawnie, ale baza nie zawiera kolekcji."
                        )
                        return

                    collection_name = collections[0]

                else:
                    collection_name = selected_object

                mongo_data = get_mongo_data(
                    data["host"],
                    data["port"],
                    data["database"],
                    collection_name=collection_name
                )

                self.display_mongo_documents(mongo_data)

                self.log(
                    f"Połączenie z MongoDB działa poprawnie. "
                    f"Wyświetlono kolekcję: {collection_name}. "
                    f"Liczba dokumentów: {len(mongo_data)}"
                )

                messagebox.showinfo(
                    "Sukces",
                    f"Połączenie z MongoDB działa poprawnie.\n"
                    f"Wyświetlono kolekcję: {collection_name}.\n"
                    f"Pobrano {len(mongo_data)} dokumentów."
                )

            except Exception as e:
                self.log(f"Błąd podczas testu połączenia z MongoDB: {str(e)}")
                messagebox.showerror("Błąd", str(e))

            return

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

        selected_object = self.selected_object.get()

        if selected_object == self.empty_object_option or selected_object == "":
            messagebox.showwarning(
                "Brak wyboru",
                "Najpierw wybierz konkretną tabelę/kolekcję albo opcję Wszystkie."
            )
            return

        if selected_object == self.all_objects_option:
            selected_object = None

        self.log(f"Rozpoczęto konwersję: {source_model} -> {target_model}")

        if source_model == "PostgreSQL" and target_model == "MongoDB":
            self.log(f"Wybrany tryb MongoDB: {self.mongo_write_mode.get()}")

        if selected_object:
            self.log(f"Wybrany obiekt do konwersji: {selected_object}")
        else:
            self.log("Wybrano konwersję wszystkich tabel/kolekcji.")

        try:
            result = convert_database(
                source_model,
                target_model,
                source_data,
                target_data,
                selected_object,
                self.mongo_write_mode.get()
            )

            self.log("Konwersja zakończona powodzeniem.")
            self.log(f"Liczba tabel/kolekcji: {result['collections_or_tables']}")
            self.log(f"Liczba rekordów/dokumentów: {result['records']}")

            metrics = result.get("metrics")

            if metrics:
                self.log("----- METRYKI KONWERSJI -----")
                self.log(f"Liczba rekordów: {metrics['records']}")
                self.log(f"Tryb: {metrics['mode']}")
                self.log(f"Konwersja [s]: {metrics['conversion_time_s']:.4f}")
                self.log(f"RAM [MB]: {metrics['ram_mb']:.2f}")
                self.log(f"Rozmiar [MB]: {metrics['database_size_mb']:.2f}")
                self.log(f"Odczyt [ms]: {metrics['read_time_ms']:.4f}")
                self.log("Metryki zapisano do pliku: conversion_metrics.txt")

            self.display_intermediate_data(result["data"])

            if metrics:
                message = (
                    f"Konwersja {source_model} -> {target_model} zakończona powodzeniem.\n\n"
                    f"Liczba tabel/kolekcji: {result['collections_or_tables']}\n"
                    f"Liczba rekordów/dokumentów: {result['records']}\n\n"
                    f"Tryb: {metrics['mode']}\n"
                    f"Konwersja [s]: {metrics['conversion_time_s']:.4f}\n"
                    f"RAM [MB]: {metrics['ram_mb']:.2f}\n"
                    f"Rozmiar [MB]: {metrics['database_size_mb']:.2f}\n"
                    f"Odczyt [ms]: {metrics['read_time_ms']:.4f}\n\n"
                    f"Zapisano do pliku: conversion_metrics.txt"
                )
            else:
                message = (
                    f"Konwersja {source_model} -> {target_model} zakończona powodzeniem.\n\n"
                    f"Liczba tabel/kolekcji: {result['collections_or_tables']}\n"
                    f"Liczba rekordów/dokumentów: {result['records']}"
                )

            messagebox.showinfo("Sukces", message)

        except NotImplementedError as e:
            self.log(str(e))
            messagebox.showinfo("Informacja", str(e))

        except Exception as e:
            self.log(f"Błąd podczas konwersji: {str(e)}")
            messagebox.showerror("Błąd", str(e))

    def clear_log(self):
        self.log_text.delete("1.0", tk.END)
        self.clear_preview()
        self.log("Log wyczyszczony.")

    def log(self, message):
        self.log_text.insert(tk.END, message + "\n")
        self.log_text.see(tk.END)


if __name__ == "__main__":
    root = tk.Tk()
    app = ConverterGUI(root)
    root.mainloop()
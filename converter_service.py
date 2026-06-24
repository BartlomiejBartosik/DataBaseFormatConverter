import os
import time
import threading
from datetime import datetime

try:
    import psutil
except ImportError:
    psutil = None

from postgres_connection import read_postgres_to_intermediate, write_intermediate_to_postgres
from mongodb_connection import (
    read_mongo_to_intermediate,
    write_intermediate_to_mongo,
    get_mongo_database_size_mb,
    measure_mongo_read_ms
)


class MemorySampler:
    def __init__(self, interval=0.05):
        self.interval = interval
        self.max_memory_mb = 0.0
        self.running = False
        self.thread = None

    def start(self):
        if psutil is None:
            self.max_memory_mb = 0.0
            return

        self.running = True
        self.thread = threading.Thread(target=self._sample_memory)
        self.thread.daemon = True
        self.thread.start()

    def stop(self):
        if psutil is None:
            return self.max_memory_mb

        self.running = False

        if self.thread is not None:
            self.thread.join()

        return self.max_memory_mb

    def _sample_memory(self):
        process = psutil.Process(os.getpid())

        while self.running:
            memory_mb = process.memory_info().rss / (1024 * 1024)

            if memory_mb > self.max_memory_mb:
                self.max_memory_mb = memory_mb

            time.sleep(self.interval)


def save_metrics_to_txt(metrics, filename="conversion_metrics.txt"):
    file_exists = os.path.exists(filename)

    with open(filename, "a", encoding="utf-8") as file:
        if not file_exists:
            file.write(
                "Data;Źródło;Cel;Liczba rekordów;Tryb;"
                "Konwersja [s];RAM [MB];Rozmiar [MB];Odczyt [ms]\n"
            )

        file.write(
            f"{metrics['timestamp']};"
            f"{metrics['source_model']};"
            f"{metrics['target_model']};"
            f"{metrics['records']};"
            f"{metrics['mode']};"
            f"{metrics['conversion_time_s']:.4f};"
            f"{metrics['ram_mb']:.2f};"
            f"{metrics['database_size_mb']:.2f};"
            f"{metrics['read_time_ms']:.4f}\n"
        )


def build_metrics(
    source_model,
    target_model,
    mongo_write_mode,
    total_records,
    conversion_time_s,
    ram_mb,
    database_size_mb,
    read_time_ms
):
    if target_model == "MongoDB":
        mode = mongo_write_mode
    else:
        mode = "-"

    return {
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "source_model": source_model,
        "target_model": target_model,
        "records": total_records,
        "mode": mode,
        "conversion_time_s": conversion_time_s,
        "ram_mb": ram_mb,
        "database_size_mb": database_size_mb,
        "read_time_ms": read_time_ms
    }


def convert_database(
    source_model,
    target_model,
    source_config,
    target_config,
    selected_object=None,
    mongo_write_mode="Embedding"
):
    if source_model == target_model:
        raise ValueError("Model źródłowy i docelowy nie mogą być takie same.")

    memory_sampler = MemorySampler()
    memory_sampler.start()

    start_time = time.perf_counter()

    try:
        intermediate_data = read_to_intermediate(
            source_model,
            source_config,
            selected_object
        )

        if not intermediate_data:
            raise ValueError("Nie znaleziono danych do konwersji.")

        write_from_intermediate(
            target_model,
            target_config,
            intermediate_data,
            mongo_write_mode
        )

        end_time = time.perf_counter()
        conversion_time_s = end_time - start_time

    finally:
        ram_mb = memory_sampler.stop()

    visible_data = {
        name: records
        for name, records in intermediate_data.items()
        if not name.startswith("__")
    }

    total_records = sum(len(records) for records in visible_data.values())

    database_size_mb = 0.0
    read_time_ms = 0.0

    if target_model == "MongoDB":
        first_collection = None

        if visible_data:
            first_collection = list(visible_data.keys())[0]

        database_size_mb = get_mongo_database_size_mb(
            target_config["host"],
            target_config["port"],
            target_config["database"]
        )

        read_time_ms = measure_mongo_read_ms(
            target_config["host"],
            target_config["port"],
            target_config["database"],
            first_collection
        )

    metrics = build_metrics(
        source_model=source_model,
        target_model=target_model,
        mongo_write_mode=mongo_write_mode,
        total_records=total_records,
        conversion_time_s=conversion_time_s,
        ram_mb=ram_mb,
        database_size_mb=database_size_mb,
        read_time_ms=read_time_ms
    )

    save_metrics_to_txt(metrics)

    return {
        "collections_or_tables": len(visible_data),
        "records": total_records,
        "data": visible_data,
        "metrics": metrics
    }


def read_to_intermediate(model, config, selected_object=None):
    if model == "PostgreSQL":
        return read_postgres_to_intermediate(
            config["host"],
            config["port"],
            config["database"],
            config["user"],
            config["password"],
            selected_object
        )

    if model == "MongoDB":
        return read_mongo_to_intermediate(
            config["host"],
            config["port"],
            config["database"],
            selected_object
        )

    raise NotImplementedError(f"Odczyt z {model} nie jest jeszcze dostępny.")


def write_from_intermediate(
    model,
    config,
    intermediate_data,
    mongo_write_mode="Embedding"
):
    if model == "PostgreSQL":
        write_intermediate_to_postgres(
            config["host"],
            config["port"],
            config["database"],
            config["user"],
            config["password"],
            intermediate_data
        )
        return

    if model == "MongoDB":
        write_intermediate_to_mongo(
            config["host"],
            config["port"],
            config["database"],
            intermediate_data,
            mongo_write_mode
        )
        return

    raise NotImplementedError(f"Zapis do {model} nie jest jeszcze dostępny.")
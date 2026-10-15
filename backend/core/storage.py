import contextlib
import json
import sqlite3
import threading
import uuid
from datetime import datetime
from pathlib import Path

import keyring
from keyring.errors import KeyringError

from .. import config
from .types import DetalleTarea, EtapaItem, Rubrica

SCHEMA = """
CREATE TABLE IF NOT EXISTS materias (
    id TEXT PRIMARY KEY,
    nombre TEXT NOT NULL,
    profesor TEXT,
    periodo TEXT,
    orden INTEGER NOT NULL DEFAULT 0,
    sincronizada_en TEXT
);
CREATE TABLE IF NOT EXISTS etapas (
    id TEXT PRIMARY KEY,
    materia_id TEXT NOT NULL REFERENCES materias(id) ON DELETE CASCADE,
    nombre TEXT NOT NULL,
    descripcion TEXT NOT NULL DEFAULT '',
    orden INTEGER NOT NULL DEFAULT 0
);
CREATE TABLE IF NOT EXISTS tareas (
    id TEXT PRIMARY KEY,
    etapa_id TEXT NOT NULL REFERENCES etapas(id) ON DELETE CASCADE,
    materia_id TEXT NOT NULL REFERENCES materias(id) ON DELETE CASCADE,
    numero TEXT NOT NULL,
    titulo TEXT NOT NULL,
    tipo TEXT NOT NULL,
    desde TEXT,
    hasta TEXT,
    puntos REAL,
    modalidad TEXT,
    estado TEXT NOT NULL DEFAULT 'pendiente',
    orden INTEGER NOT NULL DEFAULT 0
);
CREATE TABLE IF NOT EXISTS detalle (
    tarea_id TEXT PRIMARY KEY REFERENCES tareas(id) ON DELETE CASCADE,
    actividades TEXT NOT NULL DEFAULT '',
    contenido TEXT NOT NULL DEFAULT '',
    criterios_desempeno TEXT NOT NULL DEFAULT '',
    rubrica_json TEXT
);
CREATE TABLE IF NOT EXISTS insumos (
    id TEXT PRIMARY KEY,
    tarea_id TEXT NOT NULL REFERENCES tareas(id) ON DELETE CASCADE,
    tipo TEXT NOT NULL,
    original_path TEXT,
    recortada_path TEXT,
    texto TEXT,
    orden INTEGER NOT NULL DEFAULT 0,
    rotacion INTEGER NOT NULL DEFAULT 0,
    usar_recorte INTEGER NOT NULL DEFAULT 1
);
CREATE TABLE IF NOT EXISTS generaciones (
    tarea_id TEXT PRIMARY KEY REFERENCES tareas(id) ON DELETE CASCADE,
    markdown TEXT NOT NULL,
    docx_path TEXT NOT NULL,
    pdf_path TEXT NOT NULL,
    creada_en TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS settings (
    key TEXT PRIMARY KEY,
    value TEXT
);
"""

SETTING_DEFAULTS = {
    "cuenta": "",
    "nombre": "",
    "matricula": "",
    "entregar_sin_revisar": False,
    "reducir_animaciones": False,
}
BOOL_SETTINGS = {"entregar_sin_revisar", "reducir_animaciones"}


def now_iso() -> str:
    return datetime.now().isoformat(timespec="seconds")


class Credentials:
    def get(self, cuenta: str) -> str | None:
        if not cuenta:
            return None
        try:
            return keyring.get_password(config.KEYRING_SERVICE, cuenta)
        except KeyringError:
            return None

    def has(self, cuenta: str) -> bool:
        return bool(self.get(cuenta))

    def set(self, cuenta: str, password: str) -> None:
        keyring.set_password(config.KEYRING_SERVICE, cuenta, password)

    def delete(self, cuenta: str) -> None:
        with contextlib.suppress(KeyringError):
            keyring.delete_password(config.KEYRING_SERVICE, cuenta)


class Storage:
    def __init__(self, db_path: Path):
        db_path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.RLock()
        self._db = sqlite3.connect(db_path, check_same_thread=False)
        self._db.row_factory = sqlite3.Row
        self._db.execute("PRAGMA foreign_keys = ON")
        self._db.executescript(SCHEMA)
        self._db.commit()

    def close(self) -> None:
        with self._lock:
            self._db.close()

    def _all(self, sql: str, args: tuple = ()) -> list[dict]:
        with self._lock:
            return [dict(r) for r in self._db.execute(sql, args).fetchall()]

    def _one(self, sql: str, args: tuple = ()) -> dict | None:
        with self._lock:
            row = self._db.execute(sql, args).fetchone()
            return dict(row) if row else None

    def _run(self, sql: str, args: tuple = ()) -> None:
        with self._lock:
            self._db.execute(sql, args)
            self._db.commit()

    def get_settings(self) -> dict:
        rows = {r["key"]: r["value"] for r in self._all("SELECT key, value FROM settings")}
        out = {}
        for key, default in SETTING_DEFAULTS.items():
            if key not in rows or rows[key] is None:
                out[key] = default
            elif key in BOOL_SETTINGS:
                out[key] = rows[key] == "1"
            else:
                out[key] = rows[key]
        return out

    def set_settings(self, values: dict) -> None:
        with self._lock:
            for key, value in values.items():
                if key not in SETTING_DEFAULTS:
                    continue
                stored = ("1" if value else "0") if key in BOOL_SETTINGS else str(value)
                self._db.execute(
                    "INSERT INTO settings(key, value) VALUES(?, ?) "
                    "ON CONFLICT(key) DO UPDATE SET value = excluded.value",
                    (key, stored),
                )
            self._db.commit()

    def upsert_materia(self, id: str, nombre: str, orden: int = 0) -> None:
        self._run(
            "INSERT INTO materias(id, nombre, orden) VALUES(?, ?, ?) "
            "ON CONFLICT(id) DO UPDATE SET nombre = excluded.nombre, orden = excluded.orden",
            (id, nombre, orden),
        )

    def set_portada(self, id: str, profesor: str | None, periodo: str | None) -> None:
        self._run(
            "UPDATE materias SET profesor = ?, periodo = ?, sincronizada_en = ? WHERE id = ?",
            (profesor, periodo, now_iso(), id),
        )

    def list_materias(self) -> list[dict]:
        return self._all(
            "SELECT id, nombre, profesor, periodo, sincronizada_en FROM materias ORDER BY orden"
        )

    def get_materia(self, id: str) -> dict | None:
        return self._one(
            "SELECT id, nombre, profesor, periodo, sincronizada_en FROM materias WHERE id = ?",
            (id,),
        )

    def replace_estructura(self, materia_id: str, etapas: list[EtapaItem]) -> None:
        with self._lock:
            keep_etapas, keep_tareas = [], []
            for etapa in etapas:
                etapa_id = f"{materia_id}-e{etapa.orden + 1}"
                keep_etapas.append(etapa_id)
                self._db.execute(
                    "INSERT INTO etapas(id, materia_id, nombre, descripcion, orden) "
                    "VALUES(?, ?, ?, ?, ?) ON CONFLICT(id) DO UPDATE SET "
                    "nombre = excluded.nombre, descripcion = excluded.descripcion, "
                    "orden = excluded.orden",
                    (etapa_id, materia_id, etapa.nombre, etapa.descripcion, etapa.orden),
                )
                for t in etapa.tareas:
                    tarea_id = f"{materia_id}-{t.numero}"
                    keep_tareas.append(tarea_id)
                    self._db.execute(
                        "INSERT INTO tareas(id, etapa_id, materia_id, numero, titulo, tipo, "
                        "puntos, modalidad, orden) VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?) "
                        "ON CONFLICT(id) DO UPDATE SET etapa_id = excluded.etapa_id, "
                        "titulo = excluded.titulo, tipo = excluded.tipo, "
                        "puntos = COALESCE(excluded.puntos, puntos), "
                        "modalidad = COALESCE(excluded.modalidad, modalidad), "
                        "orden = excluded.orden",
                        (
                            tarea_id,
                            etapa_id,
                            materia_id,
                            t.numero,
                            t.titulo,
                            t.tipo,
                            t.puntos,
                            t.modalidad,
                            t.orden,
                        ),
                    )
            self._prune("tareas", "materia_id", materia_id, keep_tareas)
            self._prune("etapas", "materia_id", materia_id, keep_etapas)
            self._db.commit()

    def _prune(self, table: str, col: str, value: str, keep: list[str]) -> None:
        marks = ",".join("?" for _ in keep) or "''"
        self._db.execute(
            f"DELETE FROM {table} WHERE {col} = ? AND id NOT IN ({marks})",
            (value, *keep),
        )

    def list_etapas(self, materia_id: str) -> list[dict]:
        etapas = self._all(
            "SELECT id, materia_id, nombre, descripcion FROM etapas "
            "WHERE materia_id = ? ORDER BY orden",
            (materia_id,),
        )
        for e in etapas:
            e["tareas"] = self._all(
                "SELECT id, etapa_id, materia_id, numero, titulo, tipo, desde, hasta, puntos, "
                "modalidad, estado FROM tareas WHERE etapa_id = ? ORDER BY orden",
                (e["id"],),
            )
        return etapas

    def get_tarea(self, id: str) -> dict | None:
        return self._one(
            "SELECT id, etapa_id, materia_id, numero, titulo, tipo, desde, hasta, puntos, "
            "modalidad, estado FROM tareas WHERE id = ?",
            (id,),
        )

    def tarea_posicion(self, id: str) -> tuple[int, int, int] | None:
        row = self._one(
            "SELECT m.orden AS m, e.orden AS e, t.orden AS t FROM tareas t "
            "JOIN etapas e ON e.id = t.etapa_id JOIN materias m ON m.id = t.materia_id "
            "WHERE t.id = ?",
            (id,),
        )
        return (row["m"], row["e"], row["t"]) if row else None

    def set_estado(self, id: str, estado: str) -> None:
        self._run("UPDATE tareas SET estado = ? WHERE id = ?", (estado, id))

    def get_detalle(self, tarea_id: str) -> dict | None:
        row = self._one("SELECT * FROM detalle WHERE tarea_id = ?", (tarea_id,))
        if not row:
            return None
        rubrica = json.loads(row["rubrica_json"]) if row["rubrica_json"] else None
        return {
            "actividades": row["actividades"],
            "contenido": row["contenido"],
            "criterios_desempeno": row["criterios_desempeno"],
            "rubrica": rubrica,
        }

    def set_detalle(self, tarea_id: str, d: DetalleTarea) -> None:
        rubrica = json.dumps(d.rubrica.to_dict(), ensure_ascii=False) if d.rubrica else None
        with self._lock:
            self._db.execute(
                "INSERT INTO detalle(tarea_id, actividades, contenido, criterios_desempeno, "
                "rubrica_json) VALUES(?, ?, ?, ?, ?) ON CONFLICT(tarea_id) DO UPDATE SET "
                "actividades = excluded.actividades, contenido = excluded.contenido, "
                "criterios_desempeno = excluded.criterios_desempeno, "
                "rubrica_json = excluded.rubrica_json",
                (tarea_id, d.actividades, d.contenido, d.criterios_desempeno, rubrica),
            )
            self._db.execute(
                "UPDATE tareas SET desde = ?, hasta = ?, puntos = COALESCE(?, puntos), "
                "modalidad = COALESCE(?, modalidad) WHERE id = ?",
                (d.desde, d.hasta, d.puntos, d.modalidad, tarea_id),
            )
            self._db.commit()

    def get_rubrica(self, tarea_id: str) -> Rubrica | None:
        d = self.get_detalle(tarea_id)
        return Rubrica.from_dict(d["rubrica"]) if d and d["rubrica"] else None

    def list_insumos(self, tarea_id: str) -> list[dict]:
        return self._all(
            "SELECT * FROM insumos WHERE tarea_id = ? ORDER BY orden, rowid", (tarea_id,)
        )

    def get_insumo(self, id: str) -> dict | None:
        return self._one("SELECT * FROM insumos WHERE id = ?", (id,))

    def add_insumo(
        self,
        tarea_id: str,
        tipo: str,
        *,
        id: str | None = None,
        original_path: str | None = None,
        recortada_path: str | None = None,
        texto: str | None = None,
    ) -> dict:
        id = id or uuid.uuid4().hex
        row = self._one(
            "SELECT COALESCE(MAX(orden), -1) + 1 AS n FROM insumos WHERE tarea_id = ?",
            (tarea_id,),
        )
        self._run(
            "INSERT INTO insumos(id, tarea_id, tipo, original_path, recortada_path, texto, orden) "
            "VALUES(?, ?, ?, ?, ?, ?, ?)",
            (id, tarea_id, tipo, original_path, recortada_path, texto, row["n"] if row else 0),
        )
        return self.get_insumo(id)

    def update_insumo(self, id: str, **fields) -> dict | None:
        allowed = {"orden", "rotacion", "usar_recorte", "texto", "recortada_path"}
        sets = {k: v for k, v in fields.items() if k in allowed and v is not None}
        if "usar_recorte" in sets:
            sets["usar_recorte"] = 1 if sets["usar_recorte"] else 0
        if sets:
            cols = ", ".join(f"{k} = ?" for k in sets)
            self._run(f"UPDATE insumos SET {cols} WHERE id = ?", (*sets.values(), id))
        return self.get_insumo(id)

    def delete_insumo(self, id: str) -> None:
        self._run("DELETE FROM insumos WHERE id = ?", (id,))

    def get_generacion(self, tarea_id: str) -> dict | None:
        return self._one("SELECT * FROM generaciones WHERE tarea_id = ?", (tarea_id,))

    def set_generacion(self, tarea_id: str, markdown: str, docx_path: str, pdf_path: str) -> dict:
        self._run(
            "INSERT INTO generaciones(tarea_id, markdown, docx_path, pdf_path, creada_en) "
            "VALUES(?, ?, ?, ?, ?) ON CONFLICT(tarea_id) DO UPDATE SET "
            "markdown = excluded.markdown, docx_path = excluded.docx_path, "
            "pdf_path = excluded.pdf_path, creada_en = excluded.creada_en",
            (tarea_id, markdown, docx_path, pdf_path, now_iso()),
        )
        return self.get_generacion(tarea_id)

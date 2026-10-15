from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field


async def _noop_log(message: str) -> None:
    return None


async def _noop_paso(paso: str, progreso: float | None = None) -> None:
    return None


@dataclass
class Hooks:
    log: Callable[[str], Awaitable[None]] = _noop_log
    esperar_usuario: Callable[[str], Awaitable[None]] = _noop_log
    paso: Callable[[str, float | None], Awaitable[None]] = _noop_paso
    marcar_espera: Callable[[str], Awaitable[None]] = _noop_log


@dataclass
class MateriaCard:
    id: str
    nombre: str
    orden: int


@dataclass
class Portada:
    profesor: str | None
    periodo: str | None
    modalidad: str | None = None


@dataclass
class TareaItem:
    numero: str
    titulo: str
    tipo: str
    puntos: float | None
    modalidad: str | None
    orden: int


@dataclass
class EtapaItem:
    nombre: str
    descripcion: str
    orden: int
    tareas: list[TareaItem] = field(default_factory=list)


@dataclass
class RubricaNivel:
    puntos: float
    descripcion: str


@dataclass
class RubricaCriterio:
    criterio: str
    niveles: list[RubricaNivel]


@dataclass
class Rubrica:
    niveles: list[str]
    criterios: list[RubricaCriterio]

    def to_dict(self) -> dict:
        return {
            "niveles": list(self.niveles),
            "criterios": [
                {
                    "criterio": c.criterio,
                    "niveles": [
                        {"puntos": n.puntos, "descripcion": n.descripcion} for n in c.niveles
                    ],
                }
                for c in self.criterios
            ],
        }

    @classmethod
    def from_dict(cls, d: dict) -> "Rubrica":
        return cls(
            niveles=list(d["niveles"]),
            criterios=[
                RubricaCriterio(
                    criterio=c["criterio"],
                    niveles=[RubricaNivel(n["puntos"], n["descripcion"]) for n in c["niveles"]],
                )
                for c in d["criterios"]
            ],
        )


@dataclass
class DetalleTarea:
    titulo: str
    numero: str | None
    desde: str | None
    hasta: str | None
    puntos: float | None
    modalidad: str | None
    actividades: str
    contenido: str
    criterios_desempeno: str
    rubrica: Rubrica | None

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional
from datetime import date
from app.database import supabase

router = APIRouter(
    prefix="/programaciones-pago",
    tags=["Programaciones de Pago"]
)

class ProgramacionPagoCreate(BaseModel):
    evento_id: str
    evento_proveedor_id: Optional[str] = None
    origen: str = "proveedor"
    tipo_programacion: str
    monto: float
    porcentaje: Optional[float] = None
    fecha_programada: str
    estado: str = "pendiente"
    observaciones: Optional[str] = None


def calcular_estado_programacion(fecha_programada: str, estado_actual: str):
    if estado_actual in ["pagado", "pagado_sin_comprobante", "cancelado"]:
        return estado_actual

    hoy = date.today()
    fecha = date.fromisoformat(fecha_programada)

    if fecha < hoy:
        return "vencido"

    return "pendiente"


@router.get("/")
def listar_programaciones():
    response = (
        supabase
        .table("programaciones_pago")
        .select("*, eventos(nombre, cliente), evento_proveedores(servicio, monto_contratado, proveedores(razon_social))")
        .order("fecha_programada")
        .execute()
    )
    return response.data


@router.get("/evento/{evento_id}")
def listar_programaciones_por_evento(evento_id: str):
    response = (
        supabase
        .table("programaciones_pago")
        .select("*, evento_proveedores(servicio, monto_contratado, proveedores(razon_social))")
        .eq("evento_id", evento_id)
        .order("fecha_programada")
        .execute()
    )
    return response.data


@router.get("/evento-proveedor/{evento_proveedor_id}")
def listar_programaciones_por_evento_proveedor(evento_proveedor_id: str):
    response = (
        supabase
        .table("programaciones_pago")
        .select("*")
        .eq("evento_proveedor_id", evento_proveedor_id)
        .order("fecha_programada")
        .execute()
    )
    return response.data


@router.post("/")
def crear_programacion(data: ProgramacionPagoCreate):
    nueva_data = data.dict()

    nueva_data["estado"] = calcular_estado_programacion(
        nueva_data["fecha_programada"],
        nueva_data["estado"]
    )

    response = (
        supabase
        .table("programaciones_pago")
        .insert(nueva_data)
        .execute()
    )

    programacion_creada = response.data[0]

    supabase.table("alertas").insert({
        "evento_id": programacion_creada["evento_id"],
        "programacion_pago_id": programacion_creada["id"],
        "tipo_alerta": "pago_proximo",
        "origen": programacion_creada["origen"],
        "titulo": "Pago programado pendiente",
        "descripcion": f"Se registró una programación de pago por S/ {programacion_creada['monto']} para la fecha {programacion_creada['fecha_programada']}.",
        "fecha_alerta": programacion_creada["fecha_programada"],
        "estado": "pendiente"
    }).execute()

    return programacion_creada


@router.put("/{programacion_id}")
def actualizar_programacion(programacion_id: str, data: ProgramacionPagoCreate):
    nueva_data = data.dict()

    nueva_data["estado"] = calcular_estado_programacion(
        nueva_data["fecha_programada"],
        nueva_data["estado"]
    )

    response = (
        supabase
        .table("programaciones_pago")
        .update(nueva_data)
        .eq("id", programacion_id)
        .execute()
    )

    if not response.data:
        raise HTTPException(status_code=404, detail="Programación no encontrada")

    return response.data[0]


@router.delete("/{programacion_id}")
def eliminar_programacion(programacion_id: str):
    response = (
        supabase
        .table("programaciones_pago")
        .delete()
        .eq("id", programacion_id)
        .execute()
    )

    return {
        "mensaje": "Programación eliminada correctamente",
        "data": response.data
    }
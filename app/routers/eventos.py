from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional
from datetime import date
from uuid import UUID
from app.database import supabase

router = APIRouter(prefix="/eventos", tags=["Eventos"])

class EventoCreate(BaseModel):
    nombre: str
    cliente: str
    fecha_inicio: str
    fecha_fin: str
    ubicacion: Optional[str] = None
    observaciones: Optional[str] = None
    presupuesto_aprobado: float
    tipo_presupuesto: str
    monto_recibido_cliente: float = 0
    color_card: Optional[str] = None

def calcular_estado(fecha_inicio: str, fecha_fin: str):
    hoy = date.today()
    inicio = date.fromisoformat(fecha_inicio)
    fin = date.fromisoformat(fecha_fin)

    if hoy < inicio:
        return "planificacion"
    if inicio <= hoy <= fin:
        return "en_curso"
    return "finalizado"

def preparar_evento(data: dict):
    presupuesto = data.get("presupuesto_aprobado", 0)
    recibido = data.get("monto_recibido_cliente", 0)

    data["porcentaje_adelanto"] = round((recibido / presupuesto) * 100, 2) if presupuesto > 0 else 0
    data["saldo_pendiente_cliente"] = round(presupuesto - recibido, 2) if presupuesto > 0 else 0
    data["estado"] = calcular_estado(data["fecha_inicio"], data["fecha_fin"])

    return data

@router.get("/")
def listar_eventos():
    response = supabase.table("eventos").select("*").order("fecha_inicio").execute()
    return response.data

@router.get("/historial")
def listar_historial_eventos():
    response = (
        supabase
        .table("eventos")
        .select("*")
        .eq("estado", "finalizado")
        .order("fecha_inicio")
        .execute()
    )
    return response.data

@router.post("/")
def crear_evento(evento: EventoCreate):
    data = preparar_evento(evento.dict())
    response = supabase.table("eventos").insert(data).execute()
    return response.data[0]

@router.get("/{evento_id}/proveedores")
def obtener_proveedores_evento(evento_id: str):
    response = (
        supabase
        .table("evento_proveedores")
        .select("*, proveedores(*)")
        .eq("evento_id", evento_id)
        .execute()
    )

    return response.data

@router.get("/{evento_id}")
def obtener_evento(evento_id: UUID):
    response = supabase.table("eventos").select("*").eq("id", str(evento_id)).single().execute()

    if not response.data:
        raise HTTPException(status_code=404, detail="Evento no encontrado")

    return response.data

@router.put("/{evento_id}")
def actualizar_evento(evento_id: str, evento: EventoCreate):
    data = preparar_evento(evento.dict())
    response = supabase.table("eventos").update(data).eq("id", evento_id).execute()

    if not response.data:
        raise HTTPException(status_code=404, detail="Evento no encontrado")

    return response.data[0]

@router.delete("/{evento_id}")
def eliminar_evento(evento_id: str):
    response = supabase.table("eventos").delete().eq("id", evento_id).execute()
    return {"mensaje": "Evento eliminado correctamente", "data": response.data}

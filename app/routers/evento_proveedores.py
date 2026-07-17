from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional
from app.database import supabase

router = APIRouter(
    prefix="/evento-proveedores",
    tags=["Evento - Proveedores"]
)

class EventoProveedorCreate(BaseModel):
    evento_id: str
    proveedor_id: str
    servicio: str
    monto_contratado: float = 0
    archivo_cotizacion_url: Optional[str] = None
    archivo_cotizacion_nombre: Optional[str] = None
    estado: str = "Aprobado"
    observaciones: Optional[str] = None


@router.get("/")
def listar_evento_proveedores():
    response = (
        supabase
        .table("evento_proveedores")
        .select("*, eventos(nombre, cliente), proveedores(razon_social, contacto_nombre)")
        .execute()
    )
    return response.data


@router.get("/evento/{evento_id}")
def listar_proveedores_por_evento(evento_id: str):
    response = (
        supabase
        .table("evento_proveedores")
        .select("*, proveedores(*)")
        .eq("evento_id", evento_id)
        .execute()
    )
    return response.data


@router.post("/")
def asociar_proveedor_evento(data: EventoProveedorCreate):
    payload = data.dict()
    payload["estado"] = "aprobado"

    response = (
        supabase
        .table("evento_proveedores")
        .insert(payload)
        .execute()
    )

    return response.data[0]


@router.put("/{relacion_id}")
def actualizar_evento_proveedor(relacion_id: str, data: EventoProveedorCreate):
    response = (
        supabase
        .table("evento_proveedores")
        .update(data.dict())
        .eq("id", relacion_id)
        .execute()
    )

    if not response.data:
        raise HTTPException(status_code=404, detail="Relación evento-proveedor no encontrada")

    return response.data[0]


@router.delete("/{relacion_id}")
def eliminar_evento_proveedor(relacion_id: str):
    response = (
        supabase
        .table("evento_proveedores")
        .delete()
        .eq("id", relacion_id)
        .execute()
    )

    return {
        "mensaje": "Proveedor retirado del evento correctamente",
        "data": response.data
    }
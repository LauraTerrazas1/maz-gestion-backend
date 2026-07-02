from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional
from app.database import supabase

router = APIRouter(
    prefix="/personal-eventual",
    tags=["Personal Eventual"]
)


class PersonalGrupoCreate(BaseModel):
    evento_id: str
    cargo_funcion: str
    cantidad_personas: int
    pago_unitario: float
    fecha_pago: str
    metodo_pago: Optional[str] = None
    observaciones: Optional[str] = None


@router.get("/grupos")
def listar_grupos():
    response = (
        supabase
        .table("personal_eventual_grupos")
        .select("*, eventos(nombre, cliente)")
        .order("fecha_pago")
        .execute()
    )
    return response.data


@router.get("/grupos/evento/{evento_id}")
def listar_grupos_por_evento(evento_id: str):
    response = (
        supabase
        .table("personal_eventual_grupos")
        .select("*, eventos(nombre, cliente)")
        .eq("evento_id", evento_id)
        .order("fecha_pago")
        .execute()
    )
    return response.data


@router.post("/grupos")
def crear_grupo(data: PersonalGrupoCreate):
    subtotal = round(data.cantidad_personas * data.pago_unitario, 2)

    grupo_data = data.dict()
    grupo_data["estado"] = "pendiente"

    grupo_response = (
        supabase
        .table("personal_eventual_grupos")
        .insert(grupo_data)
        .execute()
    )

    if not grupo_response.data:
        raise HTTPException(status_code=400, detail="No se pudo crear el grupo")

    grupo_creado = grupo_response.data[0]

    supabase.table("alertas").insert({
        "evento_id": grupo_creado["evento_id"],
        "pago_id": None,
        "programacion_pago_id": None,
        "personal_grupo_id": grupo_creado["id"],
        "tipo_alerta": "pago_proximo",
        "origen": "personal_eventual",
        "titulo": "Pago de personal pendiente",
        "descripcion": f"Pago programado para {grupo_creado['cargo_funcion']} por S/ {subtotal}.",
        "fecha_alerta": grupo_creado["fecha_pago"],
        "estado": "pendiente",
    }).execute()

    return {
        "grupo": grupo_creado
    }

@router.put("/grupos/{grupo_id}")
def actualizar_grupo(grupo_id: str, data: PersonalGrupoCreate):
    grupo_data = data.dict()
    grupo_data["estado"] = "pendiente"

    response = (
        supabase
        .table("personal_eventual_grupos")
        .update(grupo_data)
        .eq("id", grupo_id)
        .execute()
    )

    if not response.data:
        raise HTTPException(status_code=404, detail="Grupo de personal no encontrado")

    return response.data[0]


@router.delete("/grupos/{grupo_id}")
def eliminar_grupo(grupo_id: str):
    response = (
        supabase
        .table("personal_eventual_grupos")
        .delete()
        .eq("id", grupo_id)
        .execute()
    )

    return {
        "mensaje": "Grupo de personal eliminado correctamente",
        "data": response.data
    }
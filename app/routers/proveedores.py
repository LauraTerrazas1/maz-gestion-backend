from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional
from app.database import supabase

router = APIRouter(
    prefix="/proveedores",
    tags=["Proveedores"]
)

class ProveedorCreate(BaseModel):
    tipo_proveedor: str
    razon_social: str
    documento: str
    direccion: Optional[str] = None

    representante_legal_nombre: Optional[str] = None
    representante_legal_dni: Optional[str] = None

    contacto_nombre: Optional[str] = None
    contacto_cargo: Optional[str] = None
    contacto_celular: Optional[str] = None
    contacto_correo: Optional[str] = None

    banco: Optional[str] = None
    tipo_cuenta: Optional[str] = None
    numero_cuenta: Optional[str] = None
    cci: Optional[str] = None
    moneda: str = "PEN"
    titular_cuenta: Optional[str] = None

    estado: str = "activo"


@router.get("/")
def listar_proveedores():
    response = (
        supabase
        .table("proveedores")
        .select("*")
        .order("razon_social")
        .execute()
    )
    return response.data


@router.get("/{proveedor_id}")
def obtener_proveedor(proveedor_id: str):
    response = (
        supabase
        .table("proveedores")
        .select("*")
        .eq("id", proveedor_id)
        .single()
        .execute()
    )

    if not response.data:
        raise HTTPException(status_code=404, detail="Proveedor no encontrado")

    return response.data


@router.post("/")
def crear_proveedor(proveedor: ProveedorCreate):
    response = (
        supabase
        .table("proveedores")
        .insert(proveedor.dict())
        .execute()
    )

    return response.data[0]


@router.put("/{proveedor_id}")
def actualizar_proveedor(proveedor_id: str, proveedor: ProveedorCreate):
    response = (
        supabase
        .table("proveedores")
        .update(proveedor.dict())
        .eq("id", proveedor_id)
        .execute()
    )

    if not response.data:
        raise HTTPException(status_code=404, detail="Proveedor no encontrado")

    return response.data[0]


@router.delete("/{proveedor_id}")
def desactivar_proveedor(proveedor_id: str):
    response = (
        supabase
        .table("proveedores")
        .update({
            "estado": "inactivo"
        })
        .eq("id", proveedor_id)
        .execute()
    )

    if not response.data:
        raise HTTPException(
            status_code=404,
            detail="Proveedor no encontrado"
        )

    return {
        "mensaje": "Proveedor desactivado correctamente",
        "data": response.data[0]
    }
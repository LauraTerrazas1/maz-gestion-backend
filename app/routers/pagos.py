from fastapi import APIRouter, HTTPException, UploadFile, File
from pydantic import BaseModel
from typing import Optional
from datetime import date, datetime
import os
import uuid
import re
from app.database import supabase

router = APIRouter(
    prefix="/pagos",
    tags=["Pagos"]
)

class PagoCreate(BaseModel):
    evento_id: str
    origen: str

    proveedor_id: Optional[str] = None
    evento_proveedor_id: Optional[str] = None
    personal_grupo_id: Optional[str] = None
    personal_persona_id: Optional[str] = None
    programacion_pago_id: Optional[str] = None

    tipo_pago: str
    metodo_pago: str
    monto: float

    fecha_programada: Optional[str] = None
    fecha_real_pago: Optional[str] = None

    banco: Optional[str] = None
    numero_operacion: Optional[str] = None
    observaciones: Optional[str] = None

    estado: str = "pendiente"


def calcular_estado_pago(data: dict):
    estado = data.get("estado", "pendiente")
    fecha_programada = data.get("fecha_programada")
    fecha_real_pago = data.get("fecha_real_pago")

    if estado in ["pagado", "pagado_sin_comprobante", "cancelado"]:
        return estado

    if fecha_real_pago:
        return "pagado"

    if fecha_programada:
        hoy = date.today()
        fecha = date.fromisoformat(fecha_programada)

        if fecha < hoy:
            return "vencido"

    return "pendiente"


@router.get("/")
def listar_pagos():
    response = (
        supabase
        .table("pagos")
        .select(
            "*, eventos(nombre, cliente), proveedores(razon_social), "
            "evento_proveedores(servicio, monto_contratado), "
            "personal_eventual_grupos(cargo_funcion, cantidad_personas, subtotal), "
            "comprobantes_pago(*)"
        )
        .order("fecha_creacion", desc=True)
        .execute()
)

    return response.data


@router.get("/{pago_id}")
def obtener_pago(pago_id: str):
    response = (
        supabase
        .table("pagos")
        .select(
            "*, eventos(nombre, cliente), proveedores(razon_social), "
            "evento_proveedores(servicio, monto_contratado), "
            "personal_eventual_grupos(cargo_funcion, cantidad_personas, subtotal), "
            "comprobantes_pago(*)"
        )
        .eq("id", pago_id)
        .single()
        .execute()
    )

    if not response.data:
        raise HTTPException(status_code=404, detail="Pago no encontrado")

    return response.data


@router.post("/{pago_id}/comprobante")
def subir_comprobante(pago_id: str, archivo: UploadFile = File(...)):
    allowed_types = ["application/pdf", "image/jpeg", "image/png"]
    if archivo.content_type not in allowed_types:
        raise HTTPException(
            status_code=400,
            detail=f"Tipo de archivo no permitido. Tipos aceptados: {', '.join(allowed_types)}"
        )

    try:
        archivo.file.seek(0, os.SEEK_END)
        tamano_bytes = archivo.file.tell()
        archivo.file.seek(0)
    except Exception:
        raise HTTPException(status_code=400, detail="No se pudo validar el tamaño del archivo")

    max_bytes = 10 * 1024 * 1024
    if tamano_bytes > max_bytes:
        raise HTTPException(status_code=400, detail="El archivo supera el tamaño máximo de 10 MB")

    pago_response = (
        supabase
        .table("pagos")
        .select("id, estado")
        .eq("id", pago_id)
        .single()
        .execute()
    )

    if not pago_response.data:
        raise HTTPException(status_code=404, detail="Pago no encontrado")

    pago = pago_response.data
    def limpiar_nombre(texto: str):
        texto = texto.strip().lower()
        texto = re.sub(r"[^a-zA-Z0-9._-]+", "_", texto)
        texto = re.sub(r"_+", "_", texto)
        return texto.strip("_")


    pago_detalle = (
        supabase
        .table("pagos")
        .select(
            "monto, origen, eventos(nombre), proveedores(razon_social), "
            "personal_eventual_grupos(cargo_funcion)"
        )
        .eq("id", pago_id)
        .single()
        .execute()
    )

    detalle = pago_detalle.data or {}

    evento_nombre = (detalle.get("eventos") or {}).get("nombre", "evento")

    if detalle.get("origen") == "personal_eventual":
        proveedor_nombre = (detalle.get("personal_eventual_grupos") or {}).get(
            "cargo_funcion",
            "personal_eventual"
        )
    else:
        proveedor_nombre = (detalle.get("proveedores") or {}).get(
            "razon_social",
            "proveedor"
        )

    monto_pago = detalle.get("monto", 0)

    nombre_original = os.path.basename(archivo.filename)
    extension = os.path.splitext(nombre_original)[1] or ".pdf"

    nombre_archivo = limpiar_nombre(
        f"{evento_nombre}_{proveedor_nombre}_{monto_pago}"
    )

    archivo_path = f"pagos/{pago_id}/{nombre_archivo}_{uuid.uuid4()}{extension}"

    try:
        archivo_bytes = archivo.file.read()
        supabase.storage.from_("comprobantes").upload(
            archivo_path,
            archivo_bytes,
            {"content-type": archivo.content_type}
        )
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Error al subir el archivo: {exc}")

    comprobante_data = {
        "pago_id": pago_id,
        "archivo_path": archivo_path,
        "archivo_url": archivo_path,
        "archivo_nombre": nombre_original,
        "tipo_archivo": extension.replace(".", "").lower(),
        "fecha_subida": datetime.utcnow().isoformat() + "Z",
    }

    comprobante_response = (
        supabase
        .table("comprobantes_pago")
        .insert(comprobante_data)
        .execute()
    )

    comprobante_creado = comprobante_response.data[0]
    supabase.table("alertas").update({
        "estado": "resuelta"
    }).eq("pago_id", pago_id).eq("tipo_alerta", "comprobante_pendiente").execute()

    if pago.get("estado") == "pagado_sin_comprobante":
        supabase.table("pagos").update({"estado": "pagado"}).eq("id", pago_id).execute()

    return {
        "mensaje": "Comprobante subido correctamente",
        "comprobante": comprobante_creado
    }


@router.get("/{pago_id}/comprobante-url")
def obtener_url_comprobante(pago_id: str):
    comprobante_response = (
        supabase
        .table("comprobantes_pago")
        .select("*")
        .eq("pago_id", pago_id)
        .order("fecha_subida", desc=True)
        .limit(1)
        .execute()
    )

    comprobantes = comprobante_response.data
    if not comprobantes:
        raise HTTPException(status_code=404, detail="Comprobante no encontrado")

    comprobante = comprobantes[0]

    try:
        signed = supabase.storage.from_("comprobantes").create_signed_url(
            comprobante["archivo_path"],
            300
        )
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Error al generar la URL temporal: {exc}")

    return {
        "archivo_nombre": comprobante["archivo_nombre"],
        "tipo_archivo": comprobante["tipo_archivo"],
        "signed_url": signed.get("signedUrl") or signed.get("signedURL")
    }


@router.post("/")
def crear_pago(data: PagoCreate):
    nuevo_pago = data.dict()
    nuevo_pago["estado"] = calcular_estado_pago(nuevo_pago)

    # VALIDAR SALDO DE PROVEEDOR ANTES DE INSERTAR
    if nuevo_pago.get("origen") == "proveedor" and nuevo_pago.get("evento_proveedor_id"):
        ep_id = nuevo_pago["evento_proveedor_id"]

        proveedor_evento = (
            supabase
            .table("evento_proveedores")
            .select("monto_contratado")
            .eq("id", ep_id)
            .single()
            .execute()
        )

        monto_contratado = float(proveedor_evento.data.get("monto_contratado") or 0)

        pagos_previos = (
            supabase
            .table("pagos")
            .select("monto")
            .eq("evento_proveedor_id", ep_id)
            .in_("estado", ["pagado", "pagado_sin_comprobante"])
            .execute()
        )

        total_pagado = sum(float(p.get("monto") or 0) for p in pagos_previos.data or [])
        saldo = max(monto_contratado - total_pagado, 0)

        if float(nuevo_pago["monto"]) > saldo:
            raise HTTPException(
                status_code=400,
                detail=f"El monto supera el saldo pendiente. Saldo disponible: S/ {saldo:.2f}"
            )

    response = (
        supabase
        .table("pagos")
        .insert(nuevo_pago)
        .execute()
    )

    pago_creado = response.data[0]

    if nuevo_pago["programacion_pago_id"]:
        supabase.table("programaciones_pago").update({
            "estado": pago_creado["estado"]
        }).eq("id", nuevo_pago["programacion_pago_id"]).execute()

        supabase.table("alertas").update({
            "estado": "resuelta"
        }).eq("programacion_pago_id", nuevo_pago["programacion_pago_id"]).execute()

    # RESOLVER PROGRAMACIONES Y ALERTAS DE PROVEEDOR SI YA SE PAGÓ TODO
    if pago_creado["origen"] == "proveedor" and pago_creado.get("evento_proveedor_id"):
        ep_id = pago_creado["evento_proveedor_id"]

        proveedor_evento = (
            supabase
            .table("evento_proveedores")
            .select("monto_contratado")
            .eq("id", ep_id)
            .single()
            .execute()
        )

        monto_contratado = float(proveedor_evento.data.get("monto_contratado") or 0)

        pagos_realizados = (
            supabase
            .table("pagos")
            .select("monto")
            .eq("evento_proveedor_id", ep_id)
            .in_("estado", ["pagado", "pagado_sin_comprobante"])
            .execute()
        )

        total_pagado = sum(float(p.get("monto") or 0) for p in pagos_realizados.data or [])
        saldo = max(monto_contratado - total_pagado, 0)

        if saldo <= 0:
            programaciones = (
                supabase
                .table("programaciones_pago")
                .select("id")
                .eq("evento_proveedor_id", ep_id)
                .execute()
            )

            for prog in programaciones.data or []:
                supabase.table("programaciones_pago").update({
                    "estado": "pagado"
                }).eq("id", prog["id"]).execute()

                supabase.table("alertas").update({
                    "estado": "resuelta"
                }).eq("programacion_pago_id", prog["id"]).execute()

    if pago_creado["origen"] == "personal_eventual" and pago_creado.get("personal_grupo_id"):
        grupo_id = pago_creado["personal_grupo_id"]

        grupo_response = (
            supabase
            .table("personal_eventual_grupos")
            .select("subtotal")
            .eq("id", grupo_id)
            .single()
            .execute()
        )

        subtotal_grupo = float(grupo_response.data.get("subtotal") or 0)

        pagos_realizados_response = (
            supabase
            .table("pagos")
            .select("id, monto")
            .eq("personal_grupo_id", grupo_id)
            .in_("estado", ["pagado", "pagado_sin_comprobante"])
            .execute()
        )

        total_pagado = sum(float(p.get("monto") or 0) for p in pagos_realizados_response.data or [])
        saldo = max(subtotal_grupo - total_pagado, 0)

        if saldo <= 0:
            supabase.table("personal_eventual_grupos").update({
                "estado": "pagado"
            }).eq("id", grupo_id).execute()

            supabase.table("alertas").update({
                "estado": "resuelta"
            }).eq("personal_grupo_id", grupo_id).execute()

    if pago_creado["estado"] == "pagado_sin_comprobante":
        supabase.table("alertas").insert({
            "evento_id": pago_creado["evento_id"],
            "pago_id": pago_creado["id"],
            "tipo_alerta": "comprobante_pendiente",
            "origen": pago_creado["origen"],
            "titulo": "Comprobante pendiente",
            "descripcion": "El pago fue registrado sin comprobante adjunto.",
            "fecha_alerta": date.today().isoformat(),
            "estado": "pendiente"
        }).execute()

    return pago_creado

@router.put("/{pago_id}")
def actualizar_pago(pago_id: str, data: PagoCreate):
    pago_actualizado = data.dict()
    pago_actualizado["estado"] = calcular_estado_pago(pago_actualizado)

    response = (
        supabase
        .table("pagos")
        .update(pago_actualizado)
        .eq("id", pago_id)
        .execute()
    )

    if not response.data:
        raise HTTPException(status_code=404, detail="Pago no encontrado")

    return response.data[0]


@router.delete("/{pago_id}")
def eliminar_pago(pago_id: str):
    response = (
        supabase
        .table("pagos")
        .delete()
        .eq("id", pago_id)
        .execute()
    )

    return {
        "mensaje": "Pago eliminado correctamente",
        "data": response.data
    }
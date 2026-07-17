from fastapi import APIRouter, HTTPException, UploadFile, File
from pydantic import BaseModel, Field
from typing import Optional
from app.database import supabase
import os
import re
import uuid

router = APIRouter(
    prefix="/ordenes-compra",
    tags=["Órdenes de Compra"]
)


class OrdenCompraCreate(BaseModel):
    evento_id: str
    proveedor_id: str
    evento_proveedor_id: str

    fecha_emision: Optional[str] = None

    participacion_evento: Optional[str] = None
    descripcion: Optional[str] = None

    lugar_entrega: Optional[str] = None
    fecha_requerida: Optional[str] = None

    moneda: str = "PEN"
    condiciones_pago: Optional[str] = None


    porcentaje_igv: float = Field(default=18, ge=0, le=100)

    observaciones: Optional[str] = None

    requiere_factura: bool = True
    
    archivo_cotizacion_url: Optional[str] = None
    archivo_cotizacion_nombre: Optional[str] = None


class OrdenCompraUpdate(BaseModel):
    fecha_emision: Optional[str] = None

    participacion_evento: Optional[str] = None
    descripcion: Optional[str] = None

    lugar_entrega: Optional[str] = None
    fecha_requerida: Optional[str] = None

    moneda: Optional[str] = None
    condiciones_pago: Optional[str] = None


    porcentaje_igv: Optional[float] = Field(
        default=None,
        ge=0,
        le=100
    )

    observaciones: Optional[str] = None
    
    requiere_factura: Optional[bool] = None

    archivo_cotizacion_url: Optional[str] = None
    archivo_cotizacion_nombre: Optional[str] = None


class CambioEstadoOrden(BaseModel):
    estado: str

class OrdenCompraItemCreate(BaseModel):
    descripcion: str
    cantidad: float = Field(default=1, gt=0)
    precio_unitario: float = Field(default=0, ge=0)


class OrdenCompraItemUpdate(BaseModel):
    descripcion: Optional[str] = None
    cantidad: Optional[float] = Field(default=None, gt=0)
    precio_unitario: Optional[float] = Field(default=None, ge=0)
    
def validar_evento_proveedor(
    evento_id: str,
    proveedor_id: str,
    evento_proveedor_id: str
):
    response = (
        supabase
        .table("evento_proveedores")
        .select("id, evento_id, proveedor_id")
        .eq("id", evento_proveedor_id)
        .execute()
    )

    if not response.data:
        raise HTTPException(
            status_code=404,
            detail="El proveedor asociado al evento no existe"
        )

    asociacion = response.data[0]

    if asociacion["evento_id"] != evento_id:
        raise HTTPException(
            status_code=400,
            detail="El proveedor asociado no pertenece al evento indicado"
        )

    if asociacion["proveedor_id"] != proveedor_id:
        raise HTTPException(
            status_code=400,
            detail="El proveedor no coincide con la asociación del evento"
        )
def limpiar_nombre_archivo(texto: str):
    texto = texto.strip().lower()
    texto = re.sub(r"[^a-zA-Z0-9._-]+", "_", texto)
    texto = re.sub(r"_+", "_", texto)
    return texto.strip("_")

def recalcular_totales_orden(orden_id: str):
    orden_response = (
        supabase
        .table("ordenes_compra")
        .select("id, porcentaje_igv")
        .eq("id", orden_id)
        .execute()
    )

    if not orden_response.data:
        raise HTTPException(
            status_code=404,
            detail="Orden de compra no encontrada"
        )

    porcentaje_igv = float(
        orden_response.data[0].get("porcentaje_igv") or 0
    )

    items_response = (
        supabase
        .table("orden_compra_items")
        .select("subtotal")
        .eq("orden_compra_id", orden_id)
        .execute()
    )

    subtotal = round(
        sum(
            float(item.get("subtotal") or 0)
            for item in (items_response.data or [])
        ),
        2
    )

    igv = round(subtotal * porcentaje_igv / 100, 2)
    total = round(subtotal + igv, 2)

    response = (
        supabase
        .table("ordenes_compra")
        .update({
            "subtotal": subtotal,
            "igv": igv,
            "total": total
        })
        .eq("id", orden_id)
        .execute()
    )

    if not response.data:
        raise HTTPException(
            status_code=400,
            detail="No se pudieron actualizar los totales de la orden"
        )

    return response.data[0]
@router.get("/")
def listar_ordenes_compra(
    evento_id: Optional[str] = None,
    proveedor_id: Optional[str] = None,
    estado: Optional[str] = None,
    buscar: Optional[str] = None,
):
    query = (
        supabase
        .table("ordenes_compra")
        .select(
            """
            *,
            eventos(
                nombre,
                cliente,
                fecha_inicio,
                fecha_fin,
                ubicacion
            ),
            proveedores(
                razon_social,
                documento,
                direccion,
                contacto_nombre,
                contacto_correo
            ),
            evento_proveedores(
                servicio,
                monto_contratado
            )
            """
        )
    )

    if evento_id:
        query = query.eq("evento_id", evento_id)

    if proveedor_id:
        query = query.eq("proveedor_id", proveedor_id)

    if estado:
        query = query.eq("estado", estado)

    if buscar:
        texto = buscar.strip()

        if texto:
            query = query.or_(
                f"numero_oc.ilike.%{texto}%,"
                f"descripcion.ilike.%{texto}%,"
                f"participacion_evento.ilike.%{texto}%"
            )

    response = (
        query
        .order("fecha_creacion", desc=True)
        .execute()
    )

    return response.data or []

@router.get("/evento/{evento_id}")
def listar_ordenes_por_evento(evento_id: str):
    response = (
        supabase
        .table("ordenes_compra")
        .select(
            """
            *,
            proveedores(
                razon_social,
                documento,
                direccion,
                contacto_nombre,
                contacto_correo
            ),
            evento_proveedores(
                servicio,
                monto_contratado
            )
            """
        )
        .eq("evento_id", evento_id)
        .order("fecha_creacion", desc=True)
        .execute()
    )

    return response.data or []


@router.get("/proveedor/{proveedor_id}")
def listar_ordenes_por_proveedor(proveedor_id: str):
    response = (
        supabase
        .table("ordenes_compra")
        .select(
            """
            *,
            eventos(
                nombre,
                cliente,
                fecha_inicio,
                fecha_fin,
                ubicacion
            ),
            evento_proveedores(
                servicio,
                monto_contratado
            )
            """
        )
        .eq("proveedor_id", proveedor_id)
        .order("fecha_creacion", desc=True)
        .execute()
    )

    return response.data or []
@router.post("/{orden_id}/cotizacion")
def subir_cotizacion(
    orden_id: str,
    archivo: UploadFile = File(...)
):
    tipos_permitidos = [
        "application/pdf",
        "image/jpeg",
        "image/png",
    ]

    if archivo.content_type not in tipos_permitidos:
        raise HTTPException(
            status_code=400,
            detail="Solo se permiten archivos PDF, JPG o PNG"
        )

    try:
        archivo.file.seek(0, os.SEEK_END)
        tamano_bytes = archivo.file.tell()
        archivo.file.seek(0)
    except Exception:
        raise HTTPException(
            status_code=400,
            detail="No se pudo validar el tamaño del archivo"
        )

    max_bytes = 10 * 1024 * 1024

    if tamano_bytes > max_bytes:
        raise HTTPException(
            status_code=400,
            detail="El archivo supera el tamaño máximo de 10 MB"
        )

    orden_response = (
        supabase
        .table("ordenes_compra")
        .select(
            """
            id,
            numero_oc,
            estado,
            eventos(nombre),
            proveedores(razon_social)
            """
        )
        .eq("id", orden_id)
        .single()
        .execute()
    )

    if not orden_response.data:
        raise HTTPException(
            status_code=404,
            detail="Orden de compra no encontrada"
        )

    orden = orden_response.data

    if orden["estado"] != "borrador":
        raise HTTPException(
            status_code=400,
            detail="Solo se puede adjuntar una cotización mientras la orden esté en borrador"
        )

    nombre_original = os.path.basename(
        archivo.filename or "cotizacion.pdf"
    )

    extension = os.path.splitext(nombre_original)[1].lower()

    if not extension:
        extension = ".pdf"

    evento_nombre = (
        orden.get("eventos") or {}
    ).get("nombre", "evento")

    proveedor_nombre = (
        orden.get("proveedores") or {}
    ).get("razon_social", "proveedor")

    nombre_base = limpiar_nombre_archivo(
        f"{orden['numero_oc']}_{evento_nombre}_{proveedor_nombre}_cotizacion"
    )

    archivo_path = (
        f"ordenes-compra/{orden_id}/"
        f"{nombre_base}_{uuid.uuid4()}{extension}"
    )

    try:
        archivo_bytes = archivo.file.read()

        supabase.storage.from_("cotizaciones").upload(
            archivo_path,
            archivo_bytes,
            {
                "content-type": archivo.content_type
            }
        )
    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=f"Error al subir la cotización: {exc}"
        )

    response = (
        supabase
        .table("ordenes_compra")
        .update({
            "archivo_cotizacion_url": archivo_path,
            "archivo_cotizacion_nombre": nombre_original,
        })
        .eq("id", orden_id)
        .execute()
    )

    if not response.data:
        raise HTTPException(
            status_code=400,
            detail="No se pudo vincular la cotización con la orden"
        )

    return {
        "mensaje": "Cotización subida correctamente",
        "orden": response.data[0],
    }

@router.get("/{orden_id}/cotizacion-url")
def obtener_url_cotizacion(orden_id: str):
    orden_response = (
        supabase
        .table("ordenes_compra")
        .select(
            "archivo_cotizacion_url, archivo_cotizacion_nombre"
        )
        .eq("id", orden_id)
        .single()
        .execute()
    )

    if not orden_response.data:
        raise HTTPException(
            status_code=404,
            detail="Orden de compra no encontrada"
        )

    orden = orden_response.data
    archivo_path = orden.get("archivo_cotizacion_url")

    if not archivo_path:
        raise HTTPException(
            status_code=404,
            detail="La orden no tiene una cotización adjunta"
        )

    try:
        signed = (
            supabase.storage.from_("cotizaciones").create_signed_url(
                archivo_path,
                300
            )
        )
    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=f"Error al generar la URL temporal: {exc}"
        )

    return {
        "archivo_nombre": (
            orden.get("archivo_cotizacion_nombre")
            or "Cotización"
        ),
        "signed_url": (
            signed.get("signedUrl")
            or signed.get("signedURL")
        ),
    }
    
@router.get("/{orden_id}")
def obtener_orden_compra(orden_id: str):
    response = (
        supabase
        .table("ordenes_compra")
        .select(
            """
            *,
            eventos(
                nombre,
                cliente,
                fecha_inicio,
                fecha_fin,
                ubicacion
            ),
            proveedores(
                razon_social,
                documento,
                direccion,
                representante_legal_nombre,
                contacto_nombre,
                contacto_cargo,
                contacto_celular,
                contacto_correo
            ),
            evento_proveedores(
                servicio,
                monto_contratado,
                estado
            ),
            orden_compra_items(
                id,
                descripcion,
                cantidad,
                precio_unitario,
                subtotal
            )
            """
        )
        .eq("id", orden_id)
        .execute()
    )

    if not response.data:
        raise HTTPException(
            status_code=404,
            detail="Orden de compra no encontrada"
        )

    return response.data[0]


@router.post("/")
def crear_orden_compra(data: OrdenCompraCreate):
    validar_evento_proveedor(
        evento_id=data.evento_id,
        proveedor_id=data.proveedor_id,
        evento_proveedor_id=data.evento_proveedor_id
    )

    orden_data = data.model_dump(exclude_none=True)
    # Todas las órdenes del sistema serán órdenes de compra.
    orden_data["tipo_orden"] = "compra"
    # El trigger de Supabase genera automáticamente numero_oc.
    orden_data["estado"] = "borrador"

    # Los totales se calcularán cuando agreguemos los ítems.
    orden_data["subtotal"] = 0
    orden_data["igv"] = 0
    orden_data["total"] = 0

    response = (
        supabase
        .table("ordenes_compra")
        .insert(orden_data)
        .execute()
    )

    if not response.data:
        raise HTTPException(
            status_code=400,
            detail="No se pudo crear la orden de compra"
        )

    return response.data[0]


@router.put("/{orden_id}")
def actualizar_orden_compra(
    orden_id: str,
    data: OrdenCompraUpdate
):
    orden_actual = (
        supabase
        .table("ordenes_compra")
        .select("id, estado")
        .eq("id", orden_id)
        .execute()
    )

    if not orden_actual.data:
        raise HTTPException(
            status_code=404,
            detail="Orden de compra no encontrada"
        )

    if orden_actual.data[0]["estado"] in ["finalizada", "anulada"]:
        raise HTTPException(
            status_code=400,
            detail="No se puede editar una orden finalizada o anulada"
        )

    cambios = data.model_dump(exclude_none=True)

    if not cambios:
        raise HTTPException(
            status_code=400,
            detail="No se enviaron campos para actualizar"
        )

    response = (
        supabase
        .table("ordenes_compra")
        .update(cambios)
        .eq("id", orden_id)
        .execute()
    )

    if not response.data:
        raise HTTPException(
            status_code=400,
            detail="No se pudo actualizar la orden de compra"
        )

    return response.data[0]


@router.put("/{orden_id}/estado")
def cambiar_estado_orden(
    orden_id: str,
    data: CambioEstadoOrden
):
    estados_permitidos = {
        "borrador",
        "pendiente_aprobacion",
        "pendiente_factura",
        "factura_recibida",
        "en_conformidad",
        "aprobada",
        "pagos_programados",
        "finalizada",
        "anulada",
    }

    if data.estado not in estados_permitidos:
        raise HTTPException(
            status_code=400,
            detail="Estado de orden de compra no válido"
        )

    response = (
        supabase
        .table("ordenes_compra")
        .update({"estado": data.estado})
        .eq("id", orden_id)
        .execute()
    )

    if not response.data:
        raise HTTPException(
            status_code=404,
            detail="Orden de compra no encontrada"
        )

    return response.data[0]

@router.get("/{orden_id}/items")
def listar_items_orden(orden_id: str):
    orden_response = (
        supabase
        .table("ordenes_compra")
        .select("id")
        .eq("id", orden_id)
        .execute()
    )

    if not orden_response.data:
        raise HTTPException(
            status_code=404,
            detail="Orden de compra no encontrada"
        )

    response = (
        supabase
        .table("orden_compra_items")
        .select("*")
        .eq("orden_compra_id", orden_id)
        .order("fecha_creacion")
        .execute()
    )

    return response.data or []


@router.post("/{orden_id}/items")
def crear_item_orden(
    orden_id: str,
    data: OrdenCompraItemCreate
):
    orden_response = (
        supabase
        .table("ordenes_compra")
        .select("id, estado")
        .eq("id", orden_id)
        .execute()
    )

    if not orden_response.data:
        raise HTTPException(
            status_code=404,
            detail="Orden de compra no encontrada"
        )

    if orden_response.data[0]["estado"] in ["finalizada", "anulada"]:
        raise HTTPException(
            status_code=400,
            detail="No se pueden agregar ítems a una orden finalizada o anulada"
        )

    subtotal_item = round(
        float(data.cantidad) * float(data.precio_unitario),
        2
    )

    item_data = {
        "orden_compra_id": orden_id,
        "descripcion": data.descripcion,
        "cantidad": data.cantidad,
        "precio_unitario": data.precio_unitario,
        "subtotal": subtotal_item
    }

    response = (
        supabase
        .table("orden_compra_items")
        .insert(item_data)
        .execute()
    )

    if not response.data:
        raise HTTPException(
            status_code=400,
            detail="No se pudo agregar el ítem"
        )

    orden_actualizada = recalcular_totales_orden(orden_id)

    return {
        "item": response.data[0],
        "orden": orden_actualizada
    }


@router.put("/items/{item_id}")
def actualizar_item_orden(
    item_id: str,
    data: OrdenCompraItemUpdate
):
    item_response = (
        supabase
        .table("orden_compra_items")
        .select("*")
        .eq("id", item_id)
        .execute()
    )

    if not item_response.data:
        raise HTTPException(
            status_code=404,
            detail="Ítem no encontrado"
        )

    item_actual = item_response.data[0]
    orden_id = item_actual["orden_compra_id"]

    orden_response = (
        supabase
        .table("ordenes_compra")
        .select("estado")
        .eq("id", orden_id)
        .execute()
    )

    if (
        orden_response.data
        and orden_response.data[0]["estado"] in ["finalizada", "anulada"]
    ):
        raise HTTPException(
            status_code=400,
            detail="No se puede editar un ítem de una orden finalizada o anulada"
        )

    cambios = data.model_dump(exclude_none=True)

    if not cambios:
        raise HTTPException(
            status_code=400,
            detail="No se enviaron campos para actualizar"
        )

    nueva_cantidad = float(
        cambios.get("cantidad", item_actual["cantidad"])
    )
    nuevo_precio = float(
        cambios.get("precio_unitario", item_actual["precio_unitario"])
    )

    cambios["subtotal"] = round(
        nueva_cantidad * nuevo_precio,
        2
    )

    response = (
        supabase
        .table("orden_compra_items")
        .update(cambios)
        .eq("id", item_id)
        .execute()
    )

    if not response.data:
        raise HTTPException(
            status_code=400,
            detail="No se pudo actualizar el ítem"
        )

    orden_actualizada = recalcular_totales_orden(orden_id)

    return {
        "item": response.data[0],
        "orden": orden_actualizada
    }


@router.delete("/items/{item_id}")
def eliminar_item_orden(item_id: str):
    item_response = (
        supabase
        .table("orden_compra_items")
        .select("id, orden_compra_id")
        .eq("id", item_id)
        .execute()
    )

    if not item_response.data:
        raise HTTPException(
            status_code=404,
            detail="Ítem no encontrado"
        )

    orden_id = item_response.data[0]["orden_compra_id"]

    orden_response = (
        supabase
        .table("ordenes_compra")
        .select("estado")
        .eq("id", orden_id)
        .execute()
    )

    if (
        orden_response.data
        and orden_response.data[0]["estado"] in ["finalizada", "anulada"]
    ):
        raise HTTPException(
            status_code=400,
            detail="No se puede eliminar un ítem de una orden finalizada o anulada"
        )

    response = (
        supabase
        .table("orden_compra_items")
        .delete()
        .eq("id", item_id)
        .execute()
    )

    orden_actualizada = recalcular_totales_orden(orden_id)

    return {
        "mensaje": "Ítem eliminado correctamente",
        "data": response.data,
        "orden": orden_actualizada
    }
    
@router.delete("/{orden_id}")
def eliminar_orden_compra(orden_id: str):
    orden_response = (
        supabase
        .table("ordenes_compra")
        .select("id, estado")
        .eq("id", orden_id)
        .execute()
    )

    if not orden_response.data:
        raise HTTPException(
            status_code=404,
            detail="Orden de compra no encontrada"
        )

    orden = orden_response.data[0]

    if orden["estado"] not in ["borrador", "anulada"]:
        raise HTTPException(
            status_code=400,
            detail=(
                "Solo se pueden eliminar órdenes en estado "
                "borrador o anulada"
            )
        )

    response = (
        supabase
        .table("ordenes_compra")
        .delete()
        .eq("id", orden_id)
        .execute()
    )

    return {
        "mensaje": "Orden de compra eliminada correctamente",
        "data": response.data
    }
    
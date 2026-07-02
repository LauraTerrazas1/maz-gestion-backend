from fastapi import APIRouter, HTTPException
from app.database import supabase
from datetime import date

router = APIRouter(
    prefix="/alertas",
    tags=["Alertas"]
)

@router.get("/")
def listar_alertas_pendientes():
    hoy = date.today()

    alertas_response = (
        supabase
        .table("alertas")
        .select("*")
        .eq("estado", "pendiente")
        .execute()
    )

    alertas = alertas_response.data or []

    for alerta in alertas:
        fecha_alerta = alerta.get("fecha_alerta")

        if fecha_alerta:
            fecha = date.fromisoformat(fecha_alerta)

            if alerta.get("tipo_alerta") in ["pago_proximo", "pago_pendiente"]:
                if fecha < hoy:
                    alerta["tipo_alerta"] = "pago_vencido"
                    alerta["titulo"] = "Pago vencido"
                elif fecha == hoy:
                    alerta["tipo_alerta"] = "pago_hoy"
                    alerta["titulo"] = "Pago de hoy"
                else:
                    alerta["tipo_alerta"] = "pago_proximo"
                    alerta["titulo"] = alerta.get("titulo") or "Pago próximo"

    pagos_response = (
        supabase
        .table("pagos")
        .select("*, comprobantes_pago(*)")
        .in_("estado", ["pagado", "pagado_sin_comprobante"])
        .execute()
    )

    pagos_sin_comprobante = []

    for pago in pagos_response.data or []:
        comprobantes = pago.get("comprobantes_pago") or []

        ya_tiene_alerta = any(
            alerta.get("pago_id") == pago.get("id")
            and alerta.get("tipo_alerta") == "comprobante_pendiente"
            for alerta in alertas
        )

        if len(comprobantes) == 0 and not ya_tiene_alerta:
            pagos_sin_comprobante.append({
                "id": f"calc-comprobante-{pago['id']}",
                "evento_id": pago.get("evento_id"),
                "pago_id": pago.get("id"),
                "programacion_pago_id": pago.get("programacion_pago_id"),
                "tipo_alerta": "comprobante_pendiente",
                "origen": pago.get("origen"),
                "titulo": "Comprobante pendiente",
                "descripcion": f"El pago por S/ {pago.get('monto')} no tiene comprobante adjunto.",
                "fecha_alerta": pago.get("fecha_real_pago") or pago.get("fecha_programada") or "",
                "estado": "pendiente",
            })

    return alertas + pagos_sin_comprobante


@router.get("/historial")
def listar_historial():

    response = (
        supabase
        .table("alertas")
        .select("*")
        .eq("estado", "resuelta")
        .order("fecha_alerta")
        .execute()
    )

    return response.data


@router.get("/{alerta_id}")
def obtener_alerta(alerta_id: str):

    response = (
        supabase
        .table("alertas")
        .select("*")
        .eq("id", alerta_id)
        .single()
        .execute()
    )

    if not response.data:
        raise HTTPException(
            status_code=404,
            detail="Alerta no encontrada"
        )

    return response.data


@router.put("/{alerta_id}/resolver")
def resolver_alerta(alerta_id: str):

    response = (
        supabase
        .table("alertas")
        .update({
            "estado": "resuelta"
        })
        .eq("id", alerta_id)
        .execute()
    )

    if not response.data:
        raise HTTPException(
            status_code=404,
            detail="Alerta no encontrada"
        )

    return {
        "mensaje": "Alerta resuelta correctamente",
        "data": response.data[0]
    }
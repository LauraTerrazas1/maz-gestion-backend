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
        alerta["evento_nombre"] = None
        alerta["responsable"] = None
        alerta["concepto"] = None

        if alerta.get("evento_id"):
            evento_resp = (
                supabase.table("eventos")
                .select("nombre")
                .eq("id", alerta["evento_id"])
                .single()
                .execute()
            )
            alerta["evento_nombre"] = (evento_resp.data or {}).get("nombre")

        if alerta.get("programacion_pago_id"):
            prog_resp = (
                supabase.table("programaciones_pago")
                .select("monto, evento_proveedores(servicio, proveedores(razon_social))")
                .eq("id", alerta["programacion_pago_id"])
                .single()
                .execute()
            )

            prog = prog_resp.data or {}
            ep = prog.get("evento_proveedores") or {}
            proveedor = ep.get("proveedores") or {}

            alerta["responsable"] = proveedor.get("razon_social") or "Proveedor no registrado"
            alerta["concepto"] = ep.get("servicio") or "Servicio no registrado"

        if alerta.get("personal_grupo_id"):
            grupo_resp = (
                supabase.table("personal_eventual_grupos")
                .select("cargo_funcion, cantidad_personas")
                .eq("id", alerta["personal_grupo_id"])
                .single()
                .execute()
            )

            grupo = grupo_resp.data or {}
            alerta["responsable"] = grupo.get("cargo_funcion") or "Grupo de personal eventual"
            alerta["concepto"] = f"{grupo.get('cantidad_personas') or 0} personas"

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
        .select(
            "*, comprobantes_pago(*), eventos(nombre), proveedores(razon_social), "
            "evento_proveedores(servicio), personal_eventual_grupos(cargo_funcion, cantidad_personas)"
        )
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
            if pago.get("origen") == "personal_eventual":
                responsable = (pago.get("personal_eventual_grupos") or {}).get("cargo_funcion") or "Personal eventual"
                concepto = f"{(pago.get('personal_eventual_grupos') or {}).get('cantidad_personas') or 0} personas"
            else:
                responsable = (pago.get("proveedores") or {}).get("razon_social") or "Proveedor no registrado"
                concepto = (pago.get("evento_proveedores") or {}).get("servicio") or "Servicio no registrado"

            pagos_sin_comprobante.append({
                "id": f"calc-comprobante-{pago['id']}",
                "evento_id": pago.get("evento_id"),
                "evento_nombre": (pago.get("eventos") or {}).get("nombre"),
                "pago_id": pago.get("id"),
                "programacion_pago_id": pago.get("programacion_pago_id"),
                "tipo_alerta": "comprobante_pendiente",
                "origen": pago.get("origen"),
                "responsable": responsable,
                "concepto": concepto,
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
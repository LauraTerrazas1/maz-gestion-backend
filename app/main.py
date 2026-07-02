from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import os

from app.routers.eventos import router as eventos_router
from app.routers.proveedores import router as proveedores_router
from app.routers.evento_proveedores import router as evento_proveedores_router
from app.routers.programaciones_pago import router as programaciones_pago_router
from app.routers.pagos import router as pagos_router
from app.routers.alertas import router as alertas_router
from app.routers.personal_eventual import router as personal_eventual_router

app = FastAPI(
    title="MAZ Gestión Central API",
    version="0.1.0"
)

FRONTEND_URL = os.getenv("FRONTEND_URL", "http://localhost:3000")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        FRONTEND_URL,
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(eventos_router)
app.include_router(proveedores_router)
app.include_router(evento_proveedores_router)
app.include_router(programaciones_pago_router)
app.include_router(pagos_router)
app.include_router(alertas_router)
app.include_router(personal_eventual_router)


@app.get("/")
def home():
    return {"mensaje": "API MAZ funcionando"}
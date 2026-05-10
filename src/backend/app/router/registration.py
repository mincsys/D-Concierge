from fastapi import APIRouter, FastAPI


def register_api_router(app: FastAPI, router: APIRouter) -> None:
    """FastAPIアプリへAPI routerを登録する。"""
    app.include_router(router)

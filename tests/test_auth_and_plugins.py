import unittest

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api import routes
from app.auth.auth import create_jwt_token, get_current_user
from app.auth.roles import Role
from app.plugins.manager import PluginManager


class AuthTokenTests(unittest.IsolatedAsyncioTestCase):
    async def test_create_token_accepts_sub_payload_and_decodes_user_role(self) -> None:
        token = create_jwt_token({"sub": "operator-1", "role": Role.INTEGRATOR.value})

        current_user = await get_current_user(token)

        self.assertEqual({"sub": "operator-1", "role": Role.INTEGRATOR.value}, current_user)

    async def test_admin_subject_receives_admin_role(self) -> None:
        token = create_jwt_token({"sub": "admin", "role": Role.USER.value})

        current_user = await get_current_user(token)

        self.assertEqual("admin", current_user["sub"])
        self.assertEqual(Role.ADMIN.value, current_user["role"])

    def test_auth_token_endpoint_returns_bearer_token(self) -> None:
        app = FastAPI()
        app.include_router(routes.router)
        client = TestClient(app)

        response = client.post(
            "/api/v1/auth/token",
            data={"username": "dispatcher", "password": "secret"},
        )

        self.assertEqual(200, response.status_code)
        self.assertEqual("bearer", response.json()["token_type"])
        self.assertTrue(response.json()["access_token"])

    def test_protected_plugin_list_requires_admin_role(self) -> None:
        app = FastAPI()
        app.include_router(routes.router)
        client = TestClient(app)
        user_token = create_jwt_token({"sub": "operator-1", "role": Role.USER.value})
        admin_token = create_jwt_token({"sub": "admin", "role": Role.USER.value})

        user_response = client.get(
            "/api/v1/plugins",
            headers={"Authorization": f"Bearer {user_token}"},
        )
        admin_response = client.get(
            "/api/v1/plugins",
            headers={"Authorization": f"Bearer {admin_token}"},
        )

        self.assertEqual(403, user_response.status_code)
        self.assertEqual(200, admin_response.status_code)


class PluginManagerTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self) -> None:
        PluginManager.plugins = {}
        PluginManager.scheduled_tasks = {}

    async def asyncTearDown(self) -> None:
        loaded = list(PluginManager.plugins)
        for plugin_name in loaded:
            await PluginManager.unload_plugin(plugin_name)
        PluginManager.plugins = {}
        PluginManager.scheduled_tasks = {}

    async def test_load_list_get_and_unload_plugin(self) -> None:
        load_result = await PluginManager.load_plugin("system_a")

        self.assertEqual({"status": "loaded"}, load_result)
        self.assertEqual({"system_a": "stopped"}, PluginManager.list_plugins())
        self.assertFalse(PluginManager.is_runnable("system_a"))

        data = await PluginManager.get_plugin_data("missing")
        unload_result = await PluginManager.unload_plugin("system_a")

        self.assertEqual({"error": "Plugin not found"}, data)
        self.assertEqual({"status": "unloaded"}, unload_result)

    async def test_missing_plugin_returns_error(self) -> None:
        result = await PluginManager.load_plugin("does_not_exist")

        self.assertEqual({"error": "Plugin does_not_exist not found"}, result)
        self.assertFalse(PluginManager.is_runnable("does_not_exist"))

    async def test_websocket_plugin_is_detected_as_runnable_after_load(self) -> None:
        result = await PluginManager.load_plugin("system_b")

        self.assertEqual({"status": "loaded"}, result)
        self.assertTrue(PluginManager.is_runnable("system_b"))


if __name__ == "__main__":
    unittest.main()

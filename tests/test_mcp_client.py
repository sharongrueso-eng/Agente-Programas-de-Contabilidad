"""Cliente MCP: sesión, cabeceras y desenvolvimiento de respuestas."""

import json
import unittest

from orchestrator.mcp_client import ClienteMcp, McpError


class TransporteFalso:
    def __init__(self, respuestas):
        self.respuestas = list(respuestas)
        self.llamadas = []

    def request(self, method, url, *, headers, body):
        self.llamadas.append(
            {"method": method, "url": url, "headers": dict(headers), "body": body}
        )
        return self.respuestas.pop(0)


def cliente(respuestas):
    return ClienteMcp(
        url="https://sitio/wp-json/mcp/mcp-adapter-default-server",
        headers={"Authorization": "Basic abc"},
        transporte=TransporteFalso(respuestas),
    )


class SesionTests(unittest.TestCase):
    def test_guarda_la_sesion_que_devuelve_el_saludo(self) -> None:
        c = cliente(
            [
                (200, {"mcp-session-id": "s-1"}, json.dumps({
                    "jsonrpc": "2.0", "id": 1,
                    "result": {"protocolVersion": "2025-06-18", "serverInfo": {"name": "x"}},
                }).encode()),
            ]
        )

        c.inicializar()

        self.assertEqual(c.sesion, "s-1")

    def test_las_llamadas_siguientes_llevan_sesion_y_version(self) -> None:
        c = cliente(
            [
                (200, {"mcp-session-id": "s-1"}, b'{"jsonrpc":"2.0","id":1,"result":{}}'),
                (200, {}, b'{"jsonrpc":"2.0","id":2,"result":{"tools":[]}}'),
            ]
        )
        c.inicializar()

        c.herramientas()

        cabeceras = c.transporte.llamadas[1]["headers"]
        self.assertEqual(cabeceras["Mcp-Session-Id"], "s-1")
        self.assertEqual(cabeceras["MCP-Protocol-Version"], "2025-06-18")
        self.assertEqual(cabeceras["Authorization"], "Basic abc")

    def test_el_saludo_no_lleva_sesion(self) -> None:
        c = cliente([(200, {}, b'{"jsonrpc":"2.0","id":1,"result":{}}')])

        c.inicializar()

        self.assertNotIn("Mcp-Session-Id", c.transporte.llamadas[0]["headers"])


class RespuestaTests(unittest.TestCase):
    def test_acepta_sse(self) -> None:
        cuerpo = b'event: message\ndata: {"jsonrpc":"2.0","id":2,"result":{"tools":[{"name":"x"}]}}\n\n'
        c = cliente([(200, {}, b'{"jsonrpc":"2.0","id":1,"result":{}}'), (200, {}, cuerpo)])
        c.inicializar()

        herramientas = c.herramientas()

        self.assertEqual(herramientas[0]["name"], "x")

    def test_un_error_jsonrpc_se_propaga(self) -> None:
        c = cliente([(200, {}, b'{"jsonrpc":"2.0","id":1,"result":{}}')])
        c.inicializar()
        c.transporte.respuestas.append(
            (400, {}, b'{"jsonrpc":"2.0","id":2,"error":{"code":-32600,"message":"falta cabecera"}}')
        )

        with self.assertRaises(McpError) as contexto:
            c.herramientas()

        self.assertIn("falta cabecera", str(contexto.exception))

    def test_desenvuelve_el_texto_json_del_contenido(self) -> None:
        c = cliente(
            [
                (200, {}, b'{"jsonrpc":"2.0","id":1,"result":{}}'),
                (200, {}, json.dumps({
                    "jsonrpc": "2.0", "id": 2,
                    "result": {"content": [{"type": "text", "text": '{"id": 4518}'}]},
                }).encode()),
            ]
        )
        c.inicializar()

        salida = c.ejecutar("ewpa/create-post", {"title": "x"})

        self.assertEqual(salida, {"id": 4518})

    def test_is_error_lanza_con_el_mensaje_del_servidor(self) -> None:
        c = cliente(
            [
                (200, {}, b'{"jsonrpc":"2.0","id":1,"result":{}}'),
                (200, {}, json.dumps({
                    "jsonrpc": "2.0", "id": 2,
                    "result": {
                        "isError": True,
                        "content": [{"type": "text", "text": "Ability not found"}],
                    },
                }).encode()),
            ]
        )
        c.inicializar()

        with self.assertRaises(McpError) as contexto:
            c.ejecutar("ewpa/no-existe", {})

        self.assertIn("Ability not found", str(contexto.exception))

    def test_llamar_arma_el_sobre_de_execute_ability(self) -> None:
        c = cliente(
            [
                (200, {}, b'{"jsonrpc":"2.0","id":1,"result":{}}'),
                (200, {}, b'{"jsonrpc":"2.0","id":2,"result":{"content":[]}}'),
            ]
        )
        c.inicializar()

        c.ejecutar("ewpa/update-post-meta", {"post_id": 1, "meta_key": "a", "meta_value": "b"})

        enviado = json.loads(c.transporte.llamadas[1]["body"])
        self.assertEqual(enviado["method"], "tools/call")
        self.assertEqual(enviado["params"]["name"], "mcp-adapter-execute-ability")
        self.assertEqual(enviado["params"]["arguments"]["ability_name"], "ewpa/update-post-meta")
        self.assertEqual(enviado["params"]["arguments"]["parameters"]["post_id"], 1)


if __name__ == "__main__":
    unittest.main()

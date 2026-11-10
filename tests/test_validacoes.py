"""Testes das funcoes puras usadas pelos comandos do bot."""
import importlib

import pytest

bot = importlib.import_module("bot")


class TestHostValido:
    @pytest.mark.parametrize("host", ["google.com", "8.8.8.8", "meet.woncode.com.br", "a-b.example"])
    def test_aceita_dominio_e_ip(self, host):
        assert bot.host_valido(host) is True

    @pytest.mark.parametrize("host", [
        "", None, "8.8.8.8; rm -rf /", "host com espaco", "$(whoami)", "a|b", "`id`", "a&b", "a>b", "-f",
    ])
    def test_recusa_metacaractere_e_vazio(self, host):
        assert bot.host_valido(host) is False


class TestIpValido:
    @pytest.mark.parametrize("ip", ["1.2.3.4", "0.0.0.0", "255.255.255.255", "192.168.0.1"])
    def test_aceita_ipv4(self, ip):
        assert bot.ip_valido(ip) is True

    @pytest.mark.parametrize("ip", ["", None, "1.2.3", "1.2.3.4.5", "256.1.1.1", "1.2.3.4; id", "abc"])
    def test_recusa_invalido_e_octeto_fora_da_faixa(self, ip):
        assert bot.ip_valido(ip) is False


class TestPortaValida:
    @pytest.mark.parametrize("entrada,esperado", [
        ("80", (80, "tcp")),
        ("443/tcp", (443, "tcp")),
        ("53/udp", (53, "udp")),
        ("/8080", (8080, "tcp")),
        (" 22 ", (22, "tcp")),
    ])
    def test_aceita_formatos(self, entrada, esperado):
        assert bot.porta_valida(entrada) == esperado

    @pytest.mark.parametrize("entrada", ["", None, "0", "65536", "abc", "80; id", "80/sctp", "-1"])
    def test_recusa_invalida(self, entrada):
        assert bot.porta_valida(entrada) is None


class TestAutorizacao:
    def test_autoriza_somente_o_chat_pareado(self):
        assert bot.autorizado(424242, 424242) is True

    def test_bloqueia_outro_chat(self):
        assert bot.autorizado(999, 424242) is False

    def test_fail_closed_sem_pareamento(self):
        # sem chat_id gravado nada e autorizado (era o furo antigo)
        assert bot.autorizado(424242, None) is False
        assert bot.autorizado(424242, 0) is False


class TestRunArgs:
    def test_executa_e_captura_saida(self):
        saida = bot.run_args(["echo", "ok"])
        assert saida.strip() == "ok"

    def test_nao_interpreta_metacaractere(self):
        saida = bot.run_args(["echo", "$(id); rm -rf /tmp/nao-deve-existir"])
        assert "$(id)" in saida          # veio literal, o shell nao expandiu

    def test_comando_inexistente_nao_levanta(self):
        assert bot.run_args(["comando-que-nao-existe-xyz"]) == ""

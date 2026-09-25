"""Deterministic stand-ins for the proxies and services the daily run touches.

They sit at the proxy seam on purpose: the golden test drives the real
container, discovery and video service over them, so each refactoring
milestone keeps being checked against the same inputs.
"""

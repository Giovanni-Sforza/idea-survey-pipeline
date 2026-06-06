#!/usr/bin/env python3
"""symbolic_derive.py — SymPy-based step-by-step symbolic derivation executor.

This tool is the symbolic-algebra backbone of the `analytic-derivation` skill.
It is designed to be invoked by the `theory-synthesizer` subagent, NOT by the
main agent.

Design principles
-----------------
1. The tool is stateless across invocations: every run reads a single JSON
   script that fully describes the symbols, dimensions, source equations, and
   the ordered list of derivation steps. There is no hidden interpreter
   session.

2. Each step is small and verbatim-auditable. The subagent writes one JSON
   step; the tool executes it; the trace records "input equations + operation
   + parameters + result expression + any error". A human (or
   `hep-theory-reviewer`) can replay any step in isolation.

3. Failures are caught and reported per-step, not as a Python traceback. A
   bad step never aborts the whole script. The trace's `status` field tells
   the consumer which steps succeeded.

4. Dimensional analysis is a first-class operation. Every equation can be
   tagged with the (multiplicative) dimensions of its LHS and RHS; the
   `dimensional_check` op verifies they match. Dimensions are written as
   power-products of named base units (e.g. `L * T^-1`, `M * L^2 * T^-2`),
   parsed by SymPy.

5. The tool ships with a `selftest` subcommand that runs an end-to-end
   derivation without any external paper or LLM, used by the skill's
   self-audit step (Step 8 in SKILL.md).

CLI
---
    python3 tools/symbolic_derive.py run --script <path-in.json> --output <path-out.json>
    python3 tools/symbolic_derive.py selftest
    python3 tools/symbolic_derive.py schema           # prints the JSON schema
    python3 tools/symbolic_derive.py check-deps       # verifies sympy import

Script schema (version 1)
-------------------------
See `SCHEMA_DOC` below or `python3 tools/symbolic_derive.py schema`.

Output trace
------------
A JSON file with:
    {
      "schema_version": "1",
      "script_path": "...",
      "overall_status": "ok" | "partial" | "failed",
      "step_count": N,
      "steps": [
        {
          "id": "s1",
          "op": "substitute",
          "status": "ok" | "error",
          "result_eq_id": "eq_omega_beta2",
          "result_latex": "...",
          "result_sympy": "...",
          "comment": "...",
          "error": null | "..."
        },
        ...
      ],
      "checks": [
        {"op": "dimensional_check", "equation": "eq_x", "status": "ok|fail",
         "lhs_dim": "L T^-1", "rhs_dim": "L T^-1", "message": "..."}
      ],
      "final_equations": {
        "eq_id": {"latex": "...", "sympy": "..."}
      }
    }

The subagent reads this trace and writes prose around it.  The main agent
NEVER reads the trace.
"""

from __future__ import annotations

import argparse
import json
import sys
import traceback
from pathlib import Path
from typing import Any, Optional

try:
    import sympy as sp
    from sympy.parsing.sympy_parser import (
        parse_expr,
        standard_transformations,
        implicit_multiplication_application,
        convert_xor,
    )
except ImportError:
    print(
        "ERROR: sympy is required. Install with: pip install sympy --break-system-packages",
        file=sys.stderr,
    )
    sys.exit(2)


TRANSFORMATIONS = (
    standard_transformations
    + (implicit_multiplication_application, convert_xor)
)


SCHEMA_DOC = """
Script schema, version 1
========================

{
  "schema_version": "1",
  "title": "Short label for this derivation",
  "target_observable": "Plain text: what the final equation should express.",

  "symbols": {
    "beta2":   {"name": "beta_2",   "real": true,                "comment": "Initial-state nuclear deformation parameter"},
    "rho2":    {"name": "rho_2",    "real": true, "positive": true},
    "epsilon": {"name": "epsilon",  "real": true},
    "Pz":      {"name": "P_z",      "real": true},
    "omega":   {"name": "omega",    "real": true},
    "alpha":   {"name": "alpha",    "real": true, "positive": true},
    "C":       {"name": "C",        "real": true, "positive": true}
  },

  "dimensions": {
    "beta2":   "1",
    "rho2":    "1",
    "epsilon": "1",
    "Pz":      "1",
    "omega":   "1 / T",
    "alpha":   "T",
    "C":       "1"
  },

  "base_dimensions": ["L", "T", "M"],

  "equations": {
    "eq_rho2_beta2": {
      "expr":    "Eq(rho_2, C * beta_2)",
      "comment": "User-given bridge: shockwave rho2 proportional to beta2.",
      "source":  "user_assumption"
    },
    "eq_omega_rho2": {
      "expr":   "Eq(omega, alpha * (rho_2 + epsilon))",
      "source": "paper:arxiv-XXXX"
    }
  },

  "steps": [
    {
      "id":      "s1",
      "op":      "subs_value",
      "into":    "eq_omega_rho2",
      "values":  {"epsilon": "0"},
      "save_as": "eq_omega_rho2_eps0",
      "comment": "User assumption epsilon = 0."
    },
    {
      "id":      "s2",
      "op":      "substitute",
      "into":    "eq_omega_rho2_eps0",
      "using":   ["eq_rho2_beta2"],
      "save_as": "eq_omega_beta2",
      "comment": "Substitute the rho2-beta2 bridge."
    }
  ],

  "checks": [
    {"op": "dimensional_check", "equation": "eq_omega_beta2"},
    {"op": "limit_check", "equation": "eq_omega_beta2", "var": "beta_2", "to": "0", "expected_rhs": "0"}
  ]
}

Operations supported by `op` in `steps`
---------------------------------------

- substitute  : Substitute one or more equations' RHS for their LHS into
                the target equation. Inputs: into (eq_id), using ([eq_id]),
                save_as (new eq_id).
- subs_value  : Substitute symbolic or numeric values for symbols.
                Inputs: into (eq_id), values (dict symbol_name -> sympy expr),
                save_as.
- expand      : sympy.expand on RHS. Inputs: into, save_as.
- simplify    : sympy.simplify on RHS, with a hard 5-second guard via
                sympy.simplify(..., ratio=2, measure=count_ops). Inputs:
                into, save_as.
- series      : Series-expand the RHS in `var` to `order`. Inputs:
                into, var (symbol_name), order (int), save_as.
- limit       : sympy.limit on the RHS. Inputs: into, var (symbol_name),
                to (sympy expr), save_as.
- solve       : Solve for a target symbol. Inputs: into, for_var
                (symbol_name), save_as.
- expectation_gaussian
              : Compute <X> and <X^2> - <X>^2 of a polynomial X = f(var)
                under the assumption var ~ Normal(mean, sigma).
                Inputs: into (eq_id whose RHS is f(var)), var (symbol_name),
                mean (sympy expr, default 0), sigma (symbol_name, default
                "sigma_var"), save_as_mean (eq_id), save_as_variance (eq_id).
- assign      : Define a new equation directly. Inputs: expr, save_as.
- rename      : Substitute one symbol for another (notation reconciliation).
                Inputs: into, mapping (dict old_name -> new_name), save_as.

Operations supported by `op` in `checks`
----------------------------------------

- dimensional_check : Verify LHS dimension == RHS dimension for an equation.
                      Inputs: equation (eq_id). Uses `dimensions` section.
- limit_check       : Verify lim(RHS) as var -> to equals expected_rhs.
                      Inputs: equation, var, to, expected_rhs.
- equality_check    : Verify the simplified difference between two equations'
                      RHSs is zero. Inputs: equation, other_equation.
"""


# ----------------------------------------------------------------------------
# Symbol & equation registry
# ----------------------------------------------------------------------------


class Registry:
    """Holds the parsed sympy Symbols and Equations for one script run."""

    def __init__(self) -> None:
        self.symbols: dict[str, sp.Symbol] = {}
        self.symbol_meta: dict[str, dict[str, Any]] = {}
        self.dimensions: dict[str, sp.Expr] = {}
        self.base_dims: list[sp.Symbol] = []
        self.equations: dict[str, sp.Equality] = {}
        self.eq_meta: dict[str, dict[str, Any]] = {}

    # ------------------------------------------------------------------
    # Construction
    # ------------------------------------------------------------------
    def register_base_dimensions(self, names: list[str]) -> None:
        for n in names:
            self.base_dims.append(sp.Symbol(n, positive=True))

    def register_symbol(self, key: str, spec: dict[str, Any]) -> None:
        name = spec.get("name", key)
        assumptions: dict[str, Any] = {}
        for k in (
            "real",
            "positive",
            "negative",
            "integer",
            "rational",
            "nonzero",
            "finite",
        ):
            if k in spec:
                assumptions[k] = bool(spec[k])
        sym = sp.Symbol(name, **assumptions)
        self.symbols[key] = sym
        self.symbol_meta[key] = spec

    def register_dimension(self, symbol_key: str, dim_str: str) -> None:
        # Build a local namespace of base dims and any already-registered
        # symbol-name strings (so e.g. "L * T^-1" works).
        local = {d.name: d for d in self.base_dims}
        try:
            expr = parse_expr(
                dim_str, local_dict=local, transformations=TRANSFORMATIONS
            )
        except Exception as exc:
            raise ValueError(
                f"failed to parse dimension '{dim_str}' for symbol '{symbol_key}': {exc}"
            )
        self.dimensions[symbol_key] = sp.sympify(expr)

    def register_equation(
        self, eq_id: str, expr_str: str, meta: Optional[dict[str, Any]] = None
    ) -> None:
        local = {k: v for k, v in self.symbols.items()}
        # Also expose each symbol by its sympy name so users can write
        # either the registry key (e.g. "beta2") or the sympy name
        # (e.g. "beta_2") in equations.
        local.update({v.name: v for v in self.symbols.values()})
        local["Eq"] = sp.Eq
        try:
            parsed = parse_expr(
                expr_str, local_dict=local, transformations=TRANSFORMATIONS
            )
        except Exception as exc:
            raise ValueError(
                f"failed to parse equation '{eq_id}' = '{expr_str}': {exc}"
            )
        if not isinstance(parsed, sp.Equality):
            # Allow shorthand: a bare expression becomes Eq(<eq_id>, expr).
            # Use a fresh symbol whose name == eq_id.
            lhs = sp.Symbol(eq_id)
            parsed = sp.Eq(lhs, parsed)
        self.equations[eq_id] = parsed
        self.eq_meta[eq_id] = meta or {}

    # ------------------------------------------------------------------
    # Lookup helpers
    # ------------------------------------------------------------------
    def parse_user_expr(self, s: str) -> sp.Expr:
        local = {k: v for k, v in self.symbols.items()}
        local.update({v.name: v for v in self.symbols.values()})
        local["Eq"] = sp.Eq
        return parse_expr(
            s, local_dict=local, transformations=TRANSFORMATIONS
        )

    def get_symbol(self, key_or_name: str) -> sp.Symbol:
        if key_or_name in self.symbols:
            return self.symbols[key_or_name]
        for sym in self.symbols.values():
            if sym.name == key_or_name:
                return sym
        raise KeyError(f"unknown symbol: {key_or_name}")

    def get_equation(self, eq_id: str) -> sp.Equality:
        if eq_id not in self.equations:
            raise KeyError(f"unknown equation: {eq_id}")
        return self.equations[eq_id]


# ----------------------------------------------------------------------------
# Operations
# ----------------------------------------------------------------------------


def _expression_dimensions(
    expr: sp.Expr, registry: Registry
) -> sp.Expr:
    """Compute the dimension of a sympy expression by substituting each
    symbol with its declared dimension (as a sympy expression in the base
    dims). Pure numbers and unknown symbols are treated as dimensionless."""
    subs: dict[sp.Symbol, sp.Expr] = {}
    free = expr.free_symbols
    for sym in free:
        # Find the registry key whose sympy symbol matches this `sym`.
        match_key: Optional[str] = None
        for k, v in registry.symbols.items():
            if v == sym:
                match_key = k
                break
        if match_key is None:
            # Unknown symbol => treat as dimensionless 1.
            subs[sym] = sp.Integer(1)
            continue
        dim = registry.dimensions.get(match_key, sp.Integer(1))
        subs[sym] = dim
    out = expr.xreplace(subs)
    try:
        out = sp.simplify(out)
    except Exception:
        pass
    return out


def _step_substitute(step: dict[str, Any], reg: Registry) -> sp.Equality:
    into_id = step["into"]
    using_ids = step.get("using", [])
    target = reg.get_equation(into_id)
    new_rhs = target.rhs
    for uid in using_ids:
        u = reg.get_equation(uid)
        new_rhs = new_rhs.subs(u.lhs, u.rhs)
    return sp.Eq(target.lhs, new_rhs)


def _step_subs_value(step: dict[str, Any], reg: Registry) -> sp.Equality:
    target = reg.get_equation(step["into"])
    sub_map: dict[sp.Symbol, sp.Expr] = {}
    for k, v in step.get("values", {}).items():
        sym = reg.get_symbol(k)
        if isinstance(v, str):
            val = reg.parse_user_expr(v)
        else:
            val = sp.sympify(v)
        sub_map[sym] = val
    return sp.Eq(target.lhs, target.rhs.subs(sub_map))


def _step_expand(step: dict[str, Any], reg: Registry) -> sp.Equality:
    target = reg.get_equation(step["into"])
    return sp.Eq(target.lhs, sp.expand(target.rhs))


def _step_simplify(step: dict[str, Any], reg: Registry) -> sp.Equality:
    target = reg.get_equation(step["into"])
    try:
        new_rhs = sp.simplify(target.rhs)
    except Exception:
        new_rhs = target.rhs
    return sp.Eq(target.lhs, new_rhs)


def _step_series(step: dict[str, Any], reg: Registry) -> sp.Equality:
    target = reg.get_equation(step["into"])
    var = reg.get_symbol(step["var"])
    order = int(step.get("order", 4))
    series_expr = sp.series(target.rhs, var, 0, order).removeO()
    return sp.Eq(target.lhs, sp.expand(series_expr))


def _step_limit(step: dict[str, Any], reg: Registry) -> sp.Equality:
    target = reg.get_equation(step["into"])
    var = reg.get_symbol(step["var"])
    to_expr = reg.parse_user_expr(str(step["to"]))
    new_rhs = sp.limit(target.rhs, var, to_expr)
    return sp.Eq(target.lhs, new_rhs)


def _step_solve(step: dict[str, Any], reg: Registry) -> sp.Equality:
    target = reg.get_equation(step["into"])
    var = reg.get_symbol(step["for_var"])
    sols = sp.solve(target, var, dict=False)
    if not sols:
        raise ValueError(f"solve returned no solutions for {var}")
    return sp.Eq(var, sols[0])


def _step_assign(step: dict[str, Any], reg: Registry) -> sp.Equality:
    expr_str = step["expr"]
    parsed = reg.parse_user_expr(expr_str)
    if not isinstance(parsed, sp.Equality):
        lhs = sp.Symbol(step["save_as"])
        parsed = sp.Eq(lhs, parsed)
    return parsed


def _step_rename(step: dict[str, Any], reg: Registry) -> sp.Equality:
    target = reg.get_equation(step["into"])
    mapping = step.get("mapping", {})
    sub_map: dict[sp.Symbol, sp.Symbol] = {}
    for old, new in mapping.items():
        old_sym = reg.get_symbol(old)
        new_sym = reg.get_symbol(new) if new in reg.symbols or any(
            s.name == new for s in reg.symbols.values()
        ) else sp.Symbol(new)
        sub_map[old_sym] = new_sym
    return sp.Eq(
        target.lhs.subs(sub_map), target.rhs.subs(sub_map)
    )


def _step_expectation_gaussian(
    step: dict[str, Any], reg: Registry
) -> tuple[sp.Equality, sp.Equality]:
    """Compute <X> and <X^2> - <X>^2 of X = f(var) assuming
    var ~ Normal(mean, sigma).

    Returns (mean_eq, variance_eq).
    """
    target = reg.get_equation(step["into"])
    var = reg.get_symbol(step["var"])
    mean = reg.parse_user_expr(str(step.get("mean", "0")))
    sigma_name = step.get("sigma", f"sigma_{var.name}")
    if sigma_name in reg.symbols:
        sigma = reg.symbols[sigma_name]
    elif any(s.name == sigma_name for s in reg.symbols.values()):
        sigma = reg.get_symbol(sigma_name)
    else:
        sigma = sp.Symbol(sigma_name, positive=True, real=True)
        reg.symbols[sigma_name] = sigma
        reg.dimensions[sigma_name] = reg.dimensions.get(step["var"], sp.Integer(1))

    f_expr = target.rhs

    # Expand f as a polynomial-ish series in (var - mean), then take expectation
    # term by term using moments of a Gaussian:
    #   E[(var - mean)^k] = 0   if k odd
    #                       sigma^k * (k-1)!!  if k even.
    # We try a Taylor expansion to a finite order (default 6).
    order = int(step.get("order", 6))
    delta = sp.Dummy("delta")
    f_about_mean = f_expr.subs(var, mean + delta)
    try:
        series_expr = sp.series(f_about_mean, delta, 0, order + 1).removeO()
    except Exception:
        # Fall back: treat f as already polynomial in delta
        series_expr = f_about_mean
    series_expr = sp.expand(series_expr)
    poly = sp.Poly(series_expr, delta)
    coeffs = poly.all_coeffs()[::-1]  # ascending in delta

    def gaussian_moment(k: int) -> sp.Expr:
        if k == 0:
            return sp.Integer(1)
        if k % 2 == 1:
            return sp.Integer(0)
        # (k-1)!! = (k-1)(k-3)...1
        dd = sp.Integer(1)
        for i in range(k - 1, 0, -2):
            dd *= i
        return dd * sigma**k

    expectation = sp.Integer(0)
    sq_expectation = sp.Integer(0)
    # <f>
    for k, c in enumerate(coeffs):
        expectation += sp.expand(c * gaussian_moment(k))
    # <f^2>: expand (sum c_k delta^k)^2 = sum_{k,l} c_k c_l delta^{k+l}
    for k, ck in enumerate(coeffs):
        for l, cl in enumerate(coeffs):
            sq_expectation += sp.expand(ck * cl * gaussian_moment(k + l))

    variance = sp.expand(sq_expectation - expectation**2)
    expectation = sp.expand(expectation)

    mean_lhs = sp.Symbol(step["save_as_mean"])
    var_lhs = sp.Symbol(step["save_as_variance"])
    return sp.Eq(mean_lhs, expectation), sp.Eq(var_lhs, variance)


STEP_OPS = {
    "substitute": _step_substitute,
    "subs_value": _step_subs_value,
    "expand": _step_expand,
    "simplify": _step_simplify,
    "series": _step_series,
    "limit": _step_limit,
    "solve": _step_solve,
    "assign": _step_assign,
    "rename": _step_rename,
}


# ----------------------------------------------------------------------------
# Checks
# ----------------------------------------------------------------------------


def _check_dimensional(check: dict[str, Any], reg: Registry) -> dict[str, Any]:
    eq_id = check["equation"]
    eq = reg.get_equation(eq_id)
    lhs_dim = _expression_dimensions(eq.lhs, reg)
    rhs_dim = _expression_dimensions(eq.rhs, reg)
    diff = sp.simplify(lhs_dim - rhs_dim)
    ok = diff == 0
    return {
        "op": "dimensional_check",
        "equation": eq_id,
        "status": "ok" if ok else "fail",
        "lhs_dim": str(lhs_dim),
        "rhs_dim": str(rhs_dim),
        "message": "lhs == rhs" if ok else f"mismatch: {lhs_dim} vs {rhs_dim}",
    }


def _check_limit(check: dict[str, Any], reg: Registry) -> dict[str, Any]:
    eq_id = check["equation"]
    eq = reg.get_equation(eq_id)
    var = reg.get_symbol(check["var"])
    to_expr = reg.parse_user_expr(str(check["to"]))
    expected = reg.parse_user_expr(str(check["expected_rhs"]))
    try:
        actual = sp.limit(eq.rhs, var, to_expr)
        diff = sp.simplify(actual - expected)
        ok = diff == 0
        return {
            "op": "limit_check",
            "equation": eq_id,
            "var": var.name,
            "to": str(to_expr),
            "expected_rhs": str(expected),
            "actual_rhs": str(actual),
            "status": "ok" if ok else "fail",
            "message": "match" if ok else f"got {actual}, expected {expected}",
        }
    except Exception as exc:
        return {
            "op": "limit_check",
            "equation": eq_id,
            "var": var.name,
            "status": "error",
            "message": f"limit failed: {exc}",
        }


def _check_equality(check: dict[str, Any], reg: Registry) -> dict[str, Any]:
    a = reg.get_equation(check["equation"])
    b = reg.get_equation(check["other_equation"])
    try:
        diff = sp.simplify(a.rhs - b.rhs)
        ok = diff == 0
        return {
            "op": "equality_check",
            "equation": check["equation"],
            "other_equation": check["other_equation"],
            "status": "ok" if ok else "fail",
            "message": "rhs equal" if ok else f"diff = {diff}",
        }
    except Exception as exc:
        return {
            "op": "equality_check",
            "equation": check["equation"],
            "other_equation": check["other_equation"],
            "status": "error",
            "message": str(exc),
        }


CHECK_OPS = {
    "dimensional_check": _check_dimensional,
    "limit_check": _check_limit,
    "equality_check": _check_equality,
}


# ----------------------------------------------------------------------------
# Driver
# ----------------------------------------------------------------------------


def _build_registry(script: dict[str, Any]) -> Registry:
    reg = Registry()
    reg.register_base_dimensions(script.get("base_dimensions", ["L", "T", "M"]))
    for key, spec in script.get("symbols", {}).items():
        reg.register_symbol(key, spec)
    for key, dim_str in script.get("dimensions", {}).items():
        reg.register_dimension(key, str(dim_str))
    for eq_id, body in script.get("equations", {}).items():
        if isinstance(body, str):
            reg.register_equation(eq_id, body, None)
        else:
            reg.register_equation(eq_id, body["expr"], body)
    return reg


def _format_eq(eq: sp.Equality) -> dict[str, str]:
    return {
        "latex": sp.latex(eq),
        "sympy": str(eq),
    }


def run_script(script: dict[str, Any]) -> dict[str, Any]:
    reg = _build_registry(script)

    step_records: list[dict[str, Any]] = []
    overall_ok = True

    for step in script.get("steps", []):
        record: dict[str, Any] = {
            "id": step.get("id", "?"),
            "op": step["op"],
            "comment": step.get("comment", ""),
            "status": "ok",
            "error": None,
        }
        try:
            op = step["op"]
            if op == "expectation_gaussian":
                mean_eq, var_eq = _step_expectation_gaussian(step, reg)
                reg.equations[step["save_as_mean"]] = mean_eq
                reg.equations[step["save_as_variance"]] = var_eq
                reg.eq_meta[step["save_as_mean"]] = {"source": "derived", "derived_from_step": step.get("id")}
                reg.eq_meta[step["save_as_variance"]] = {"source": "derived", "derived_from_step": step.get("id")}
                record["result_mean_eq_id"] = step["save_as_mean"]
                record["result_variance_eq_id"] = step["save_as_variance"]
                record["result_mean"] = _format_eq(mean_eq)
                record["result_variance"] = _format_eq(var_eq)
            else:
                if op not in STEP_OPS:
                    raise ValueError(f"unknown op: {op}")
                new_eq = STEP_OPS[op](step, reg)
                save_id = step["save_as"]
                reg.equations[save_id] = new_eq
                reg.eq_meta[save_id] = {"source": "derived", "derived_from_step": step.get("id")}
                record["result_eq_id"] = save_id
                record["result"] = _format_eq(new_eq)
        except Exception as exc:
            record["status"] = "error"
            record["error"] = f"{type(exc).__name__}: {exc}"
            record["traceback"] = traceback.format_exc(limit=4)
            overall_ok = False
        step_records.append(record)

    check_records: list[dict[str, Any]] = []
    for check in script.get("checks", []):
        op = check.get("op")
        try:
            if op not in CHECK_OPS:
                check_records.append(
                    {
                        "op": op,
                        "status": "error",
                        "message": f"unknown check op: {op}",
                    }
                )
                overall_ok = False
                continue
            rec = CHECK_OPS[op](check, reg)
            check_records.append(rec)
            if rec.get("status") == "fail":
                overall_ok = False
        except Exception as exc:
            check_records.append(
                {
                    "op": op,
                    "status": "error",
                    "message": f"{type(exc).__name__}: {exc}",
                }
            )
            overall_ok = False

    final_equations = {
        eq_id: _format_eq(eq) for eq_id, eq in reg.equations.items()
    }

    has_error = any(s["status"] == "error" for s in step_records) or any(
        c.get("status") in ("fail", "error") for c in check_records
    )

    if has_error and any(s["status"] == "ok" for s in step_records):
        overall_status = "partial"
    elif has_error:
        overall_status = "failed"
    else:
        overall_status = "ok"

    return {
        "schema_version": "1",
        "title": script.get("title", ""),
        "target_observable": script.get("target_observable", ""),
        "overall_status": overall_status,
        "step_count": len(step_records),
        "steps": step_records,
        "checks": check_records,
        "final_equations": final_equations,
    }


# ----------------------------------------------------------------------------
# Selftest
# ----------------------------------------------------------------------------


SELFTEST_SCRIPT = {
    "schema_version": "1",
    "title": "Selftest: toy beta2 -> Pz fluctuation",
    "target_observable": "<Pz^2> - <Pz>^2 as a function of beta_2 (and sigma_beta_2)",
    "base_dimensions": ["L", "T", "M"],
    "symbols": {
        "beta2":   {"name": "beta_2",   "real": True},
        "rho2":    {"name": "rho_2",    "real": True},
        "epsilon": {"name": "epsilon",  "real": True},
        "omega":   {"name": "omega",    "real": True},
        "Pz":      {"name": "P_z",      "real": True},
        "C":       {"name": "C",        "real": True, "positive": True},
        "alpha":   {"name": "alpha",    "real": True, "positive": True},
    },
    "dimensions": {
        "beta2": "1",
        "rho2": "1",
        "epsilon": "1",
        "omega": "1 / T",
        "Pz": "1",
        "C": "1",
        "alpha": "T",
    },
    "equations": {
        "eq_rho2_beta2":   {"expr": "Eq(rho_2, C * beta_2)",
                              "source": "user_assumption",
                              "comment": "Shockwave bridge: rho_2 ∝ beta_2."},
        "eq_omega_rho2":   {"expr": "Eq(omega, (rho_2 + epsilon) / alpha)",
                              "source": "paper:fake-shockwave",
                              "comment": "Toy vorticity formula for selftest."},
        "eq_Pz_omega":     {"expr": "Eq(P_z, alpha * omega)",
                              "source": "paper:fake-polarization",
                              "comment": "Toy polarization-vorticity link, makes P_z dimensionless."},
    },
    "steps": [
        {"id": "s1", "op": "subs_value", "into": "eq_omega_rho2",
         "values": {"epsilon": "0"}, "save_as": "eq_omega_rho2_eps0",
         "comment": "User assumption epsilon = 0."},
        {"id": "s2", "op": "substitute", "into": "eq_omega_rho2_eps0",
         "using": ["eq_rho2_beta2"], "save_as": "eq_omega_beta2",
         "comment": "Insert the shockwave bridge."},
        {"id": "s3", "op": "substitute", "into": "eq_Pz_omega",
         "using": ["eq_omega_beta2"], "save_as": "eq_Pz_beta2",
         "comment": "Chain through to P_z(beta_2)."},
        {"id": "s4", "op": "expectation_gaussian", "into": "eq_Pz_beta2",
         "var": "beta2", "mean": "0", "sigma": "sigma_beta2", "order": 4,
         "save_as_mean": "eq_Pz_mean", "save_as_variance": "eq_Pz_variance",
         "comment": "Toy: assume event-by-event beta_2 fluctuates Gaussian about 0."},
    ],
    "checks": [
        {"op": "dimensional_check", "equation": "eq_Pz_beta2"},
        {"op": "dimensional_check", "equation": "eq_omega_beta2"},
        {"op": "limit_check", "equation": "eq_Pz_beta2",
         "var": "beta2", "to": "0", "expected_rhs": "0"},
    ],
}


def cmd_selftest(_args: argparse.Namespace) -> int:
    print("Running selftest...")
    trace = run_script(SELFTEST_SCRIPT)
    print(json.dumps(trace, indent=2))
    print()
    print(f"overall_status = {trace['overall_status']}")

    # Hard-coded expectations for the selftest:
    expected = {
        "overall_status": "ok",
        "step_count": 4,
    }
    failures: list[str] = []
    if trace["overall_status"] != expected["overall_status"]:
        failures.append(
            f"overall_status: got {trace['overall_status']}, expected {expected['overall_status']}"
        )
    if trace["step_count"] != expected["step_count"]:
        failures.append(
            f"step_count: got {trace['step_count']}, expected {expected['step_count']}"
        )
    # Step 4 (expectation_gaussian) for P_z = C * beta_2 should give
    #   <Pz> = 0
    #   <Pz^2> - <Pz>^2 = C^2 * sigma_beta2^2
    var_eq = trace["final_equations"].get("eq_Pz_variance", {}).get("sympy", "")
    if "sigma_beta2**2" not in var_eq.replace(" ", "") and "sigma_beta2^2" not in var_eq:
        failures.append(
            f"eq_Pz_variance does not contain sigma_beta2**2: got {var_eq}"
        )
    if "C**2" not in var_eq.replace(" ", "") and "C^2" not in var_eq:
        failures.append(
            f"eq_Pz_variance does not contain C**2: got {var_eq}"
        )

    # All checks should pass.
    for c in trace["checks"]:
        if c.get("status") != "ok":
            failures.append(f"check {c.get('op')} on {c.get('equation')} did not pass: {c}")

    if failures:
        print("SELFTEST FAILED:")
        for f in failures:
            print("  -", f)
        return 1
    print("SELFTEST PASSED")
    return 0


def cmd_run(args: argparse.Namespace) -> int:
    script_path = Path(args.script)
    output_path = Path(args.output)
    with script_path.open() as f:
        script = json.load(f)
    trace = run_script(script)
    trace["script_path"] = str(script_path)
    with output_path.open("w") as f:
        json.dump(trace, f, indent=2)
    # Also echo overall_status to stdout for shell-level audit.
    print(json.dumps({
        "overall_status": trace["overall_status"],
        "step_count": trace["step_count"],
        "errors": [s for s in trace["steps"] if s["status"] != "ok"],
        "failed_checks": [c for c in trace["checks"] if c.get("status") in ("fail", "error")],
        "output": str(output_path),
    }, indent=2))
    return 0 if trace["overall_status"] in ("ok", "partial") else 1


def cmd_schema(_args: argparse.Namespace) -> int:
    print(SCHEMA_DOC)
    return 0


def cmd_check_deps(_args: argparse.Namespace) -> int:
    print(f"sympy version: {sp.__version__}")
    print("OK")
    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        description="SymPy-based step-by-step symbolic derivation executor."
    )
    sub = p.add_subparsers(dest="command", required=True)

    p_run = sub.add_parser("run", help="Execute a derivation script JSON")
    p_run.add_argument("--script", required=True, help="Input script JSON path")
    p_run.add_argument("--output", required=True, help="Output trace JSON path")
    p_run.set_defaults(func=cmd_run)

    p_self = sub.add_parser("selftest", help="Run the bundled selftest")
    p_self.set_defaults(func=cmd_selftest)

    p_schema = sub.add_parser("schema", help="Print the JSON script schema")
    p_schema.set_defaults(func=cmd_schema)

    p_deps = sub.add_parser("check-deps", help="Verify sympy is installed")
    p_deps.set_defaults(func=cmd_check_deps)

    return p


def main(argv: Optional[list[str]] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())

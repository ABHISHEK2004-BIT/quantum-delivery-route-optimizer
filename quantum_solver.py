
"""Small-instance QAOA TSP experiment using Qiskit Optimization."""

import time
import numpy as np


def solve_qaoa(distance_matrix, reps=1, maxiter=3):
    try:
        from qiskit_optimization import QuadraticProgram
        from qiskit_optimization.converters import QuadraticProgramToQubo
        from qiskit_algorithms import QAOA
        from qiskit_algorithms.optimizers import COBYLA
        from qiskit.primitives import StatevectorSampler
        from qiskit_optimization.algorithms import MinimumEigenOptimizer

    except ImportError as exc:
        raise ImportError(
            "Qiskit packages are missing. Run: "
            "python -m pip install qiskit qiskit-algorithms "
            "qiskit-optimization"
        ) from exc

    # Validate distance matrix
    d = np.asarray(distance_matrix, dtype=float)

    if d.ndim != 2 or d.shape[0] != d.shape[1]:
        raise ValueError("Distance matrix must be square.")

    n = d.shape[0]

    if n < 3 or n > 4:
        raise ValueError(
            "QAOA supports 3-4 total locations in this demo."
        )

    if not np.isfinite(d).all():
        raise ValueError("Distance matrix contains invalid values.")

    if reps < 1 or maxiter < 1:
        raise ValueError("reps and maxiter must be positive.")

    # Create the TSP binary optimization model
    qp = QuadraticProgram("delivery_tsp")

    for i in range(n):
        for t in range(n):
            qp.binary_var(name=f"x_{i}_{t}")

    # Minimize the distance travelled between consecutive positions
    quadratic = {}

    for t in range(n):
        next_t = (t + 1) % n

        for i in range(n):
            for j in range(n):
                if i != j:
                    quadratic[
                        (f"x_{i}_{t}", f"x_{j}_{next_t}")
                    ] = float(d[i, j])

    qp.minimize(quadratic=quadratic)

    # Each city must appear exactly once
    for i in range(n):
        qp.linear_constraint(
            linear={f"x_{i}_{t}": 1 for t in range(n)},
            sense="==",
            rhs=1,
            name=f"city_once_{i}",
        )

    # Each position must contain exactly one city
    for t in range(n):
        qp.linear_constraint(
            linear={f"x_{i}_{t}": 1 for i in range(n)},
            sense="==",
            rhs=1,
            name=f"position_once_{t}",
        )

    # Fix the depot at position zero
    qp.linear_constraint(
        linear={"x_0_0": 1},
        sense="==",
        rhs=1,
        name="depot_first",
    )

    for t in range(1, n):
        qp.linear_constraint(
            linear={f"x_0_{t}": 1},
            sense="==",
            rhs=0,
            name=f"depot_not_{t}",
        )

    # Convert constraints into a QUBO model
    qubo = QuadraticProgramToQubo().convert(qp)

    # Configure QAOA with a local statevector sampler
    sampler = StatevectorSampler(seed=123)

    qaoa = QAOA(
        sampler=sampler,
        optimizer=COBYLA(maxiter=int(maxiter)),
        reps=int(reps),
    )

    # Solve and measure runtime
    start_time = time.perf_counter()

    result = MinimumEigenOptimizer(qaoa).solve(qubo)

    elapsed = time.perf_counter() - start_time

    # FIX: Build a compatible variable-name-to-index mapping.
    # Do not use qubo.get_variable_index(), which may be unavailable.
    variable_index = {
        variable.name: index
        for index, variable in enumerate(qubo.variables)
    }

    values = np.asarray(result.x, dtype=float)

    # Decode the city at every route position
    route = []

    for t in range(n):
        selected = [
            i
            for i in range(n)
            if values[variable_index[f"x_{i}_{t}"]] > 0.5
        ]

        if len(selected) != 1:
            raise RuntimeError(
                "QAOA returned a non-feasible route. "
                "Use the classical route or try another QAOA run."
            )

        route.append(selected[0])

    # Validate the decoded route
    if (
        route[0] != 0
        or len(set(route)) != n
        or set(route) != set(range(n))
    ):
        raise RuntimeError(
            "QAOA returned an invalid route. "
            "The classical result remains the recommended route."
        )

    # Close the tour by returning to the depot
    route.append(0)

    # Calculate actual route distance from the original matrix
    cost = sum(
        float(d[route[k], route[k + 1]])
        for k in range(n)
    )

    details = {
        "algorithm": "QAOA",
        "repetitions": int(reps),
        "optimizer_iterations": int(maxiter),
        "qubits_in_assignment_encoding": n * n,
        "runtime_seconds": round(elapsed, 3),
        "result_status": str(result.status),
        "note": (
            "Heuristic simulator result. "
            "No quantum advantage is implied."
        ),
    }

    return route, float(cost), details

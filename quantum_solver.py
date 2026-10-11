"""Small-instance QAOA TSP experiment using Qiskit Optimization."""
import numpy as np

def solve_qaoa(distance_matrix, reps=1, maxiter=5):
    try:
        from qiskit_optimization import QuadraticProgram
        from qiskit_optimization.converters import QuadraticProgramToQubo
        from qiskit_algorithms import QAOA
        from qiskit_algorithms.optimizers import COBYLA
        from qiskit.primitives import StatevectorSampler
        from qiskit_optimization.algorithms import MinimumEigenOptimizer
    except ImportError as exc:
        raise ImportError("Qiskit packages are missing. Install the requirements.txt file.") from exc

    d = np.asarray(distance_matrix, dtype=float)
    n = len(d)
    if d.ndim != 2 or d.shape[0] != d.shape[1]:
        raise ValueError("Distance matrix must be square.")
    if n < 3 or n > 4:
        raise ValueError("QAOA demo supports 3–4 total locations because the model uses n² binary variables.")

    qp = QuadraticProgram("delivery_tsp")
    for i in range(n):
        for t in range(n):
            qp.binary_var(name=f"x_{i}_{t}")

    quadratic = {}
    for t in range(n):
        nt = (t + 1) % n
        for i in range(n):
            for j in range(n):
                if i != j:
                    quadratic[(f"x_{i}_{t}", f"x_{j}_{nt}")] = float(d[i, j])
    qp.minimize(quadratic=quadratic)

    for i in range(n):
        qp.linear_constraint(linear={f"x_{i}_{t}": 1 for t in range(n)}, sense="==", rhs=1, name=f"city_once_{i}")
    for t in range(n):
        qp.linear_constraint(linear={f"x_{i}_{t}": 1 for i in range(n)}, sense="==", rhs=1, name=f"position_once_{t}")
    qp.linear_constraint(linear={f"x_{0}_0": 1}, sense="==", rhs=1, name="depot_first")
    for t in range(1, n):
        qp.linear_constraint(linear={f"x_{0}_{t}": 1}, sense="==", rhs=0, name=f"depot_not_{t}")

    qubo = QuadraticProgramToQubo().convert(qp)
    sampler = StatevectorSampler(seed=123)
    qaoa = QAOA(sampler=sampler, optimizer=COBYLA(maxiter=int(maxiter)), reps=int(reps))
    result = MinimumEigenOptimizer(qaoa).solve(qubo)
    values = result.x
    variable_index = {
        variable.name: index
        for index, variable in enumerate(qubo.variables)
    }
    route = []
    for t in range(n):
        selected = [i for i in range(n) if values[variable_index[f"x_{i}_{t}"]] > 0.5]
        if len(selected) != 1:
            raise RuntimeError("QAOA returned a non-feasible tour. Try another run or rely on the classical result.")
        route.append(selected[0])
    if route[0] != 0 or len(set(route)) != n:
        raise RuntimeError("QAOA returned an invalid tour. The classical route remains available.")
    route.append(0)
    cost = sum(float(d[route[k], route[k+1]]) for k in range(n))
    details = {
        "algorithm": "QAOA",
        "repetitions": int(reps),
        "optimizer_iterations": int(maxiter),
        "qubits_in_assignment_encoding": n*n,
        "result_status": str(result.status),
        "note": "Heuristic simulator result; no quantum advantage is implied.",
    }
    return route, float(cost), details

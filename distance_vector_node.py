from simulator.node import Node
import json

class Distance_Vector_Node(Node):
    """
    Distance Vector algorithm + full path to prevent count-to-infinity loops.

    Each node maintains:
      - neighbor_lat: direct costs to neighbors
      - routes: dest -> {"cost": float, "next": int, "path": [int,...]}
      - neighbor_routes: neighbor -> dest -> {"cost": float, "path": [int,...]} (as advertised)

    Messages:
      {"type":"DV_PATH","origin":<id>,
       "routes": { "<dest>": {"cost": <float>, "path": [<int>, ...]}, ... } }
    """

    def __init__(self, id):
        super().__init__(id)

        self.neighbor_lat = {}       # neighbor -> latency
        self.neighbor_routes = {}    # neighbor -> advertised route map
        self.neighbor_last_update = {}  # neighbor -> last time we received an update

        # Our selected routes: dest -> dict(cost, next, path)
        self.routes = {
            self.id: {"cost": 0.0, "next": self.id, "path": [self.id]}
        }

    def __str__(self):
        # Compact dump
        items = []
        for d in sorted(self.routes.keys()):
            r = self.routes[d]
            items.append(f"{d}: cost={r['cost']} next={r['next']} path={r['path']}")
        return (
            f"Node {self.id} (DISTANCE_VECTOR_PATH)\n"
            f"  neighbors={dict(self.neighbor_lat)}\n"
            f"  routes:\n    " + "\n    ".join(items)
        )

    def link_has_been_updated(self, neighbor, latency):
        # latency = -1 if delete a link
        neighbor = int(neighbor)
        latency = float(latency)

        if latency == -1:
            self.neighbor_lat.pop(neighbor, None)
            self.neighbor_routes.pop(neighbor, None)
            self.neighbor_last_update.pop(neighbor, None)
        else:
            self.neighbor_lat[neighbor] = latency

        changed = self._recompute_routes()
        if changed:
            self._broadcast_routes()

    def process_incoming_routing_message(self, m):
        msg = json.loads(m)

        if not isinstance(msg, dict) or msg.get("type") != "DV_PATH":
            return

        origin = int(msg["origin"])

        # Ignore vectors from non-neighbors (stale senders)
        if origin not in self.neighbor_lat:
            return

        raw_routes = msg.get("routes", {})
        if not isinstance(raw_routes, dict):
            return

        parsed = {}
        for d_str, entry in raw_routes.items():
            d = int(d_str)
            cost = float(entry["cost"])
            path = entry["path"]
            if not isinstance(path, list):
                continue
            path = [int(x) for x in path]

            # Basic sanity: advertised path should start at origin
            if len(path) == 0 or path[0] != origin:
                continue

            parsed[d] = {"cost": cost, "path": path}

        # Handle out-of-order message delivery at the same simulation time
        current_time = self.get_time()
        last_update_time = self.neighbor_last_update.get(origin, -1)
        old_routes = self.neighbor_routes.get(origin, {})
        
        if current_time == last_update_time and len(parsed) < len(old_routes):
            # Same time as last update but fewer routes - likely an older message
            # arriving out of order due to heap scheduling. Merge to keep more info.
            self.neighbor_routes[origin] = {**old_routes, **parsed}
        else:
            # Different time (newer message) or more routes - trust this message
            self.neighbor_routes[origin] = parsed
        
        self.neighbor_last_update[origin] = current_time

        changed = self._recompute_routes()
        if changed:
            self._broadcast_routes()

    def get_next_hop(self, destination):
        destination = int(destination)

        if destination == self.id:
            return self.id

        r = self.routes.get(destination)
        return -1 if r is None else r["next"]

    def _broadcast_routes(self):
        """
        Advertise our current route set (cost + full path) to neighbors.
        """
        payload = {
            "type": "DV_PATH",
            "origin": self.id,
            "routes": {
                str(d): {"cost": r["cost"], "path": r["path"]}
                for d, r in self.routes.items()
            },
        }
        self.send_to_neighbors(json.dumps(payload))

    def _recompute_routes(self):
        """
        Recompute routes using neighbors' advertised paths (path-vector loop check).

        Candidate via neighbor n to destination d:
          cost = cost_to_n + adv_cost(n->d)
          path = [self.id] + adv_path(n->d)

        Reject candidate if self.id appears in adv_path (loop).
        """
        INF = float("inf")

        new_routes = {
            self.id: {"cost": 0.0, "next": self.id, "path": [self.id]}
        }

        # Direct neighbors are always candidates
        for n, w in self.neighbor_lat.items():
            new_routes[n] = {"cost": w, "next": n, "path": [self.id, n]}

        # Consider all destinations neighbors talk about
        candidates = set(new_routes.keys())
        for n, adv in self.neighbor_routes.items():
            candidates.update(adv.keys())

        for d in candidates:
            if d == self.id:
                continue

            best = new_routes.get(d, {"cost": INF, "next": -1, "path": []})

            # Try each neighbor as next hop
            for n, w in self.neighbor_lat.items():
                adv = self.neighbor_routes.get(n)
                if not adv:
                    continue
                adv_entry = adv.get(d)
                if not adv_entry:
                    continue

                adv_cost = adv_entry["cost"]
                adv_path = adv_entry["path"]

                # Loop prevention: if we already appear in neighbor's path, skip
                if self.id in adv_path:
                    continue

                cand_cost = w + adv_cost

                # Prefer lower cost; tie-break by shorter path then smaller next hop (optional stability)
                cand_key = (cand_cost, len(adv_path) + 1, n)
                best_key = (best["cost"], len(best["path"]), best["next"])
                if cand_key < best_key:
                    best = {"cost": cand_cost, "next": n, "path": [self.id] + adv_path}

            if best["cost"] < INF:
                new_routes[d] = best

        changed = (new_routes != self.routes)
        self.routes = new_routes
        return changed
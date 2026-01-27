from simulator.node import Node
import json
import heapq

class Link_State_Node(Node):
    """
    Link-State routing node for the simulator.

    - Keeps direct neighbor latencies (neighbor_lat)
    - Floods LSAs (as JSON strings) when local links change or new LSAs are learned
    - Maintains an LSDB: newest LSA per origin (by seq)
    - Runs Dijkstra on the merged LSDB graph to compute next-hop routing_table
    """

    def __init__(self, id):
        super().__init__(id)

        # Direct neighbor view: neighbor_id -> latency
        self.neighbor_lat = {}

        # Link-State Database:
        # origin_id -> {"seq": int, "neighbors": {nbr_id: latency, ...}}
        self.lsdb = {}

        # Local sequence number for LSAs originated by this node
        self.seq = 0

        # Computed routing state
        self.routing_table = {}  # dest -> next_hop
        self.dist = {}           # dest -> shortest distance

        # Install initial (empty) self LSA
        self.lsdb[self.id] = {"seq": self.seq, "neighbors": {}}

    def __str__(self):
        # Useful for DUMP_NODE
        lines = [
            f"Node {self.id} (LINK_STATE)",
            f"  time={self.get_time()}",
            f"  neighbors={dict(self.neighbor_lat)}",
            f"  seq={self.seq}",
            f"  routing_table={dict(self.routing_table)}",
        ]
        return "\n".join(lines)

    def link_has_been_updated(self, neighbor, latency):
        # latency = -1 if delete a link
        try:
            neighbor = int(neighbor)
        except Exception:
            return

        if latency == -1:
            self.neighbor_lat.pop(neighbor, None)
        else:
            self.neighbor_lat[neighbor] = int(latency)

        # Originate and flood a new LSA, then recompute routes
        self._originate_and_flood_lsa()

    def process_incoming_routing_message(self, m):
        """
        Receives an LSA (JSON string). If it's newer than what we have for that origin,
        install it, flood it onward, and recompute routes.
        """
        try:
            msg = json.loads(m)
        except Exception:
            return

        if not isinstance(msg, dict) or msg.get("type") != "LSA":
            return

        try:
            origin = int(msg["origin"])
            incoming_seq = int(msg["seq"])
        except Exception:
            return

        # Don't re-process our own LSAs received back
        if origin == self.id:
            return

        raw_neighbors = msg.get("neighbors", {})
        incoming_neighbors = {}

        # JSON keys become strings; convert back to int
        if isinstance(raw_neighbors, dict):
            for k, v in raw_neighbors.items():
                try:
                    nk = int(k)
                    nv = int(v)
                except Exception:
                    continue
                if nv >= 0:
                    incoming_neighbors[nk] = nv

        current = self.lsdb.get(origin)
        if current is not None:
            try:
                if incoming_seq <= int(current.get("seq", -1)):
                    return  # old/duplicate
            except Exception:
                pass

        # Install
        self.lsdb[origin] = {"seq": incoming_seq, "neighbors": incoming_neighbors}

        # Flood onward (sequence checks stop endless re-processing)
        self.send_to_neighbors(m)

        # Recompute routes
        self._recompute_routes()

    def get_next_hop(self, destination):
        try:
            destination = int(destination)
        except Exception:
            return -1

        if destination == self.id:
            return self.id
        return self.routing_table.get(destination, -1)

    def _originate_and_flood_lsa(self):
        self.seq += 1

        lsa = {
            "type": "LSA",
            "origin": self.id,
            "seq": self.seq,
            # JSON keys must be strings
            "neighbors": {str(nbr): int(lat) for nbr, lat in self.neighbor_lat.items()},
        }

        # Install our own latest into LSDB
        self.lsdb[self.id] = {"seq": self.seq, "neighbors": dict(self.neighbor_lat)}

        # Flood
        self.send_to_neighbors(json.dumps(lsa))

        # Recompute
        self._recompute_routes()

    def _build_merged_adjacency(self):
        """
        Merge LSDB into an undirected adjacency dict:
          adj[u][v] = latency

        We treat any advertised neighbor relationship as an undirected edge,
        matching the simulator's nx.Graph() behavior.
        """
        adj = {}

        def add_edge(u, v, w):
            adj.setdefault(u, {})
            adj.setdefault(v, {})
            adj[u][v] = w
            adj[v][u] = w

        for origin, rec in self.lsdb.items():
            try:
                u = int(origin)
            except Exception:
                continue

            neighbors = rec.get("neighbors", {})
            if not isinstance(neighbors, dict):
                continue

            for nbr, lat in neighbors.items():
                try:
                    v = int(nbr)
                    w = int(lat)
                except Exception:
                    continue
                if w >= 0:
                    add_edge(u, v, w)

        return adj

    def _recompute_routes(self):
        """
        Dijkstra from self.id over merged LSDB graph.
        Produces:
          - self.dist[dst]
          - self.routing_table[dst] = next hop neighbor
        """
        adj = self._build_merged_adjacency()
        src = self.id

        if src not in adj:
            self.dist = {}
            self.routing_table = {}
            return

        INF = float("inf")
        dist = {src: 0}
        first_hop = {}  # node -> first hop from src
        pq = [(0, src)]

        while pq:
            d, u = heapq.heappop(pq)
            if d != dist.get(u, INF):
                continue

            for v, w in adj.get(u, {}).items():
                nd = d + w
                cur = dist.get(v, INF)

                if nd < cur:
                    dist[v] = nd
                    if u == src:
                        first_hop[v] = v
                    else:
                        # u must have a first hop if it isn't src and is reachable
                        first_hop[v] = first_hop.get(u, -1)
                    heapq.heappush(pq, (nd, v))

        self.dist = dist
        self.routing_table = dict(first_hop)
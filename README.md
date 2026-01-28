# Routesim2

This is a simple network routing simulator written in Python.  It was primarily written by Kaiyu Hou, with minor tweaks by Steve Tarzia.  This code is based on the C++ Routesim code written by Peter Dinda.

This code is the basis for a programming project for Northwestern's University's EECS-340 Introduction to Computer Networking.

### Prerequisites:

This code is written for Python 3 and it was tested on version 3.5.  Run the following to install the two required packages:

    $ pip install --user networkx matplotlib

### Running:

    $ python3 sim.py GENERIC demo.event
    
The first parameter can be either GENERIC, LINK_STATE, or DISTANCE_VECTOR.  The second parameter specifies the input file.

### Routing Algorithm Implementations:

#### LINK_STATE

The Link-State implementation (`link_state_node.py`) uses the link-state routing protocol:

- **Link-State Database (LSDB):** Each node maintains a database containing the complete network topology as learned from Link-State Advertisements (LSAs).
- **LSA Flooding:** When a node's local links change, it originates a new LSA with an incremented sequence number and floods it to all neighbors. Nodes forward new LSAs they receive (based on sequence number freshness) to prevent duplicates.
- **Dijkstra's Algorithm:** After any LSDB update, the node runs Dijkstra's shortest-path algorithm on the merged graph to compute the routing table (next-hop for each destination).

#### DISTANCE_VECTOR

The Distance-Vector implementation (`distance_vector_node.py`) uses a path-vector variant of the Bellman-Ford algorithm:

- **Distance Vectors with Paths:** Each node maintains its best-known cost and full path to every destination, sharing this information with neighbors.
- **Loop Prevention:** Uses path vectors to detect loops. If a node sees itself in an advertised path, it rejects that route. This prevents the ***count-to-infinity problem.***
- **Triggered Updates:** When routes change (due to link updates or received advertisements), the node recomputes its routes and broadcasts updates only if changes occurred.
- **Route Selection:** Prefers lower cost; ties are broken by shorter path length, then smaller next-hop ID for stability.

### Event commands:
     0. # [comment]
        e.g. # this is a comment

     1. [Time] ADD_NODE [ID], # [ID] is any hashable value
        e.g., 10 ADD_NODE 1
     2. [Time] ADD_LINK [ID1] [ID2] [LATENCY], # will create a new node if does not exist
        e.g., 10 ADD_LINK 1 2 10
     3. [Time] DELETE_NODE [ID], # [ID] is any hashable value
        e.g., 10 DELETE_NODE 1
     4. [Time] CHANGE_LINK [ID1] [ID2] [LATENCY], # will create a new node if does not exist
        e.g., 10 CHANGE_LINK 1 2 10
     5. [Time] DELETE_LINK [ID1] [ID2], # will send latency -1 to node1 and node 2
        e.g., 10 DELETE_LINK 1 2

     6. [Time] PRINT [Text]
        e.g. 10 PRINT "Debug information"
     7. [Time] DRAW_TOPOLOGY
        e.g. 10 DRAW_TOPOLOGY
     8. [Time] DRAW_PATH [ID1] [ID2]  # Draw shortest path from ID1 to ID2, Green path: correct path, Red path: your path
        e.g. 1000 DRAW_PATH 1 2
     9. [Time] DRAW_TREE [ID] # Draw shortest path tree, take ID as root
        e.g. 1000 DRAW_TREE 1

     10. [Time] DUMP_NODE [ID]
        e.g. 10 DUMP_NODE 1
     11. [Time] DUMP_SIM
        e.g. 1 DUMP_SIM # It will print topology and event stack. For debug purpose.


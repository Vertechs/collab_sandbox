## Next To Do
----
Test new consumer/producer handling
More nodes, test linking

## In Progress
----

### Master Clock:
- Read system time and publish to `@zvez/util/time`


### Zvez Node:
- Parent class of all nodes
- Pub/Sub to global orchestration channels
- 




## Misc
### global keys:
- `@zvez/*` - All network traffic
- `@zvez/global/[requests, responses]` - All requests from weaver nodes, response from nodes when needed
- `@zvez/global/[producers, consumers]` - Response from worker nodes for echo requests or auto publishing when joining the network
- `@zvez/global/bootstap/*` - New joining nodes to peers to reinitialize previous edges
# V1 GPU provider control surfaces

_Verified 2026-07-21 against current first-party documentation and published API schemas. This resolves the decision question in “Validate the V1 GPU provider control surfaces”; it does not substitute for an account-backed provisioning smoke test._

## Resolution

Keep **Runpod, Hyperstack, Verda, and generic manual SSH** in V1, but do not pretend that they share one machine lifecycle. The common architecture is:

1. a direct, provider-specific REST adapter for discovery, provisioning, resource identity, billing state, and release;
2. one provider-agnostic SSH workload plane for Commander bootstrap, execution, logs, metrics, and artifact transfer; and
3. manual SSH as the same workload plane without any provider control plane.

Provider CLIs are useful onboarding and diagnostic tools, not Battleground's integration contract. Runpod and Verda publish capable cross-platform CLIs, while the reviewed Hyperstack documentation exposes REST and client libraries but no equivalent first-party infrastructure CLI. Shelling out to CLIs would therefore create three different installation, credential, output-version, and error boundaries without eliminating the SSH workload plane. The providers' REST APIs are the consistent automation surface.

No provider exposes a portable API for starting a long-lived arbitrary Python process, preserving its complete stdout/stderr, reporting a user-defined Objective Metric, and recovering the stream after the desktop disconnects. That protocol remains Battleground-owned.

## Current capability matrix

| Concern | Runpod | Hyperstack | Verda | Manual SSH |
| --- | --- | --- | --- | --- |
| Compute model | Linux container-based Pod | Linux GPU VM | Linux GPU VM | User-provisioned Linux host/VM/container |
| Provisioning surface | GA REST/OpenAPI; GraphQL still exposes detailed GPU availability/pricing; official `runpodctl` | Versioned REST; official SDKs/libraries and Terraform/MCP are optional layers | REST/OpenAPI; official CLI, Python/Go SDKs, Terraform/OpenTofu | None |
| Bootstrap | Image or reusable Pod template; container entrypoint/start command | Image plus cloud-init `user_data` | Image plus first-deploy startup script | Idempotent first SSH connection |
| Workload access | Proxied basic SSH everywhere; direct public-IP TCP SSH is required for SCP/SFTP | Public IP, firewall rule, imported key, standard SSH | Public IP, imported key, standard SSH; CLI can open SSH | Supplied host, port, user, key, host-key fingerprint, and optional jump-host details |
| Durable storage | Pod volume disk survives stop but belongs to the Pod; Secure Cloud network volume survives Pod deletion but is datacenter-bound | Root disk survives VM lifetime and compatible hibernation; ephemeral disk does not; SSV is independent but must be detached before hibernate/delete to stay readily reusable | Block volumes are independently managed and deletion accepts an explicit retain/delete selection; SFS is location-bound | Unknown until probed; Battleground cannot infer provider durability |
| Billing-ending pause | Stop releases GPU billing for a volume-disk Pod; a Pod with a network volume cannot stop and must be terminated | Stop (`SHUTOFF`) remains fully billed; supported hibernation releases hardware but continues root-storage, volume, and retained-IP billing | Shutdown remains billed. Delete compute while retaining selected volumes is the documented economical idle path | None; stopping the workload says nothing about infrastructure billing |
| Resume constraint | Restart may return zero GPUs; public IP/port mapping can change | Restore needs the same flavor in stock; public IP normally changes | Recreate from retained volumes; see the hibernation inconsistency below | Reconnect only if the user-managed target still exists |
| Stock and prices | REST resource data plus GraphQL GPU availability/pricing; Pod responses expose effective hourly cost | Flavor and stock APIs; account Pricebook is authoritative; billing APIs expose usage/cost | Public instance types and availability; balance/cost APIs and CLI cost views | None |
| Provider logs/metrics | Console container/system logs and Pod telemetry, not the durable Experiment stream | Lifecycle events, requested console logs, and CPU/RAM/network/disk metrics; not the Objective Metric stream | Infrastructure activity history; not the Objective Metric stream | None |

## Provider findings

### Runpod

Runpod has the most complete self-service Pod automation surface. Its REST API manages Pods, templates, network volumes, registry credentials, and billing, with an OpenAPI schema for client generation. The Pod creation request accepts cloud tier, GPU candidates and count, CUDA constraints, container image or template, storage, ports, and environment. Its GraphQL API remains a documented way to query a GPU type's detailed pricing and availability. [`REST API overview`](https://docs.runpod.io/api-reference/overview), [`create Pod`](https://docs.runpod.io/api-reference/pods/POST/pods), [`GPU availability and pricing`](https://docs.runpod.io/sdks/graphql/manage-pods)

`runpodctl` has binaries for macOS, Linux, and Windows and manages Pods, GPU discovery, templates, storage, SSH setup, account details, and billing. It also exposes create-time `--stop-after` and `--terminate-after` safety timers. This makes it a good user escape hatch and diagnostic reference, but direct REST avoids requiring another executable and credential store inside Battleground. [`runpodctl overview`](https://docs.runpod.io/runpodctl/overview), [`Pod commands`](https://docs.runpod.io/runpodctl/reference/runpodctl-pod)

SSH has two materially different capabilities. Runpod's proxied “basic SSH” works without a public IP but does **not** support SCP or SFTP. Full SSH requires a Pod/template that runs `sshd`, exposes TCP 22, and receives a public IP; only that form supports the file-transfer behavior Commander needs. Community Cloud addresses can change after restart or migration, and external port mappings change on reset, so the adapter must rediscover connection details from the Pod ID. [`SSH modes`](https://docs.runpod.io/pods/configuration/use-ssh), [`TCP mapping behavior`](https://docs.runpod.io/pods/configuration/expose-ports)

Storage determines lifecycle. Stopping clears container disk, preserves the Pod's volume disk, releases GPU compute, and continues volume-disk billing. A Pod with an attached network volume cannot be stopped; it must be terminated, while the network volume survives independently. Network volumes are Secure-Cloud-only, constrain deployment to their datacenter, and do not automatically replicate. Runpod bills compute and Pod-local storage by the second and network volumes hourly; stopped storage remains billable. [`Pod lifecycle`](https://docs.runpod.io/pods/manage-pods), [`Pod pricing`](https://docs.runpod.io/pods/pricing), [`network volumes`](https://docs.runpod.io/storage/network-volumes)

**V1 consequence:** default to on-demand Secure Cloud, request full TCP SSH, and treat volume-disk Pods and network-volume Pods as different capability profiles. Persist the Pod ID, never the public address as identity. A network-volume run uses **release and recreate**, not stop/resume.

### Hyperstack

Hyperstack's versioned REST API is sufficient for a native adapter: environments and regions, keypairs, images, GPU flavors and live stock, VM creation with cloud-init, firewall/public-IP setup, lifecycle mutations, volumes, account pricebook, and billing history. VM creation is asynchronous (`CREATING` → `BUILD` → `ACTIVE`), so an HTTP success is not “ready”; Battleground must persist the VM ID and reconcile until both `ACTIVE` and an SSH-reachable public IP are present, then wait for cloud-init completion. [`API VM quickstart`](https://docs.hyperstack.cloud/docs/api-reference/getting-started-api/create-virtual-machine/), [`resource pricing and Pricebook`](https://docs.hyperstack.cloud/docs/billing/pricebook/), [`billing APIs`](https://docs.hyperstack.cloud/docs/api-reference/billing/)

Lifecycle labels have economic meaning. `SHUTOFF` retains the allocated hardware and is fully billed. Hibernation deallocates CPU/GPU/RAM and preserves the root disk in billed Cloud-SSD; ephemeral storage is lost, attached SSVs continue billing, and restoring requires the same flavor to be back in stock. Public IP is released by default. Delete ends VM billing. [`VM states and billing`](https://docs.hyperstack.cloud/docs/billing/states-and-billing/), [`hibernation`](https://docs.hyperstack.cloud/docs/virtual-machines/hibernation/)

An attached SSV enters `RESERVED` when its VM is hibernated or deleted; while reserved it remains billed and cannot be normally reattached. Hyperstack explicitly recommends detaching it first. If the VM was deleted while the SSV remained attached, support may be required to recover the volume to `AVAILABLE`. [`detach guidance`](https://docs.hyperstack.cloud/docs/storage/volumes/detaching-a-volume/), [`reserved-volume recovery`](https://docs.hyperstack.cloud/docs/storage/volumes/reserved-volumes/)

Hyperstack exposes infrastructure console logs and performance metrics, but the current metrics API documents CPU, RAM, network, and disk—not the user-authored Objective Metric or a durable process log. Commander must collect GPU and training telemetry itself. [`VM performance metrics`](https://docs.hyperstack.cloud/docs/api-reference/core-resources/virtual-machines/retrieve-metrics/), [`VM console logs`](https://docs.hyperstack.cloud/docs/api-reference/get-vm-logs)

**V1 consequence:** offer separate **Stop (still fully billed)**, **Hibernate (partially billed; restore capacity not guaranteed)**, and **Delete** consequences. Detach SSVs transactionally before hibernate/delete, and rediscover the public IP after restore.

### Verda

Verda now has the broadest optional tooling surface: a public REST/OpenAPI API, official Python and Go SDKs, GA Terraform/OpenTofu support, and a cross-platform CLI with macOS, Linux, Windows x86_64, and Windows ARM64 binaries. The CLI supports interactive and non-interactive provisioning, JSON/YAML output, stock discovery, SSH, volumes, templates/startup scripts, cost estimates, balance/runway views, and an `--agent` mode. Battleground should still call the documented REST API directly; the CLI is excellent for onboarding, diagnostics, and comparing adapter behavior. [`Verda resources`](https://docs.verda.com/resources/resources-overview/), [`Verda CLI`](https://docs.verda.com/cli/), [`current OpenAPI schema`](https://api.verda.com/v1/openapi.json)

Provisioning selects a location, instance type, OS image, SSH keys, startup script, and OS/additional volumes. The public API exposes instance types, per-location availability, images, locations, SSH keys, scripts, volumes, balance, and instance lifecycle. As of the current schema, `location_code` is mandatory and authenticated requests are limited to 500 per project per minute and 60 per method/path per minute, with `429` and `Retry-After` behavior. Mutations can return asynchronous `202` results and bulk `207` partial failures, so requests must be reconciled per resource ID. [`API change log`](https://docs.verda.com/welcome-to-verda/release-notes/verda-api-changes/), [`current OpenAPI schema`](https://api.verda.com/v1/openapi.json)

Storage is separate from compute: block volumes can be detached and reattached, while an instance-delete request selects which volumes to delete. Defaults are inconsistent across surfaces—the console guide says no storage is selected for deletion, while the OpenAPI operation says omitting `volume_ids` deletes the OS volume and detaches the rest—so Battleground must always send and display an explicit per-volume policy. SFS can be shared by multiple instances but only within one location. PAYG is charged in prepaid 10-minute increments, with unused time refunded in the next billing period when the instance is terminated early. [`volume lifecycle`](https://docs.verda.com/infrastructure-as-code/terraform/storage-volumes/), [`shutdown and delete`](https://docs.verda.com/cpu-and-gpu-instances/shutdown-hibernate-and-delete/), [`current OpenAPI schema`](https://api.verda.com/v1/openapi.json), [`SFS location constraint`](https://docs.verda.com/storage/shared-filesystems-sfs/editing-share-settings/), [`instance billing and setup`](https://docs.verda.com/cpu-and-gpu-instances/set-up-a-gpu-instance/)

There is a material documentation conflict around **hibernate**. The current CLI page says `verda vm hibernate` saves state and can resume later. The lifecycle guide says hibernate was removed because it was equivalent to deleting the instance while retaining storage. The current OpenAPI operation still accepts `hibernate`, but its own description says the instance must first be shut down, all volumes are detached, and the instance is deleted; the delete request describes an empty `volume_ids` list as the behavior “previously known as hibernate.” [`CLI instance actions`](https://docs.verda.com/cli/instances/), [`shutdown and delete`](https://docs.verda.com/cpu-and-gpu-instances/shutdown-hibernate-and-delete/), [`current OpenAPI schema`](https://api.verda.com/v1/openapi.json)

**V1 consequence:** do not promise restoration of the same Verda instance. Model the economical operation as **Release compute and retain selected volumes**, then create a replacement. Treat a returned `hibernate` capability as destructive instance release until an account-backed test proves otherwise. Shutdown is an operational state for volume work, not a cost-saving pause.

### Generic manual SSH

Manual SSH is a workload attachment, not a cloud adapter. It can execute commands and multiplex stdout, stderr, and additional channels over one encrypted connection, but SSH does not define provider provisioning, resource identity, GPU stock, price, storage durability, or a billing-ending operation. Closing a channel also does not constitute a durable workload supervisor. [`SSH connection protocol`](https://datatracker.ietf.org/doc/html/rfc4254)

V1 should accept an explicit target profile containing host, port, username, private-key reference, expected host-key fingerprint (or one-time user-confirmed trust), and optional jump host. Key authentication is the baseline. Battleground then probes, without mutating the machine, for Linux architecture, Python, writable capacity, GPU/driver visibility, SFTP support, a usable archive transfer command, and a way to supervise a detached process. The runner installation is idempotent and user-space capable; root access is not a universal requirement.

The app must label manual targets honestly:

- **Stop Research Run** can stop Commander remotely.
- **Disconnect** can close SSH while the detached runner continues.
- **Release compute** is unavailable because Battleground has no provider authority.
- Cost, stock, snapshots, disk persistence, and host recovery are **user-managed/unknown**.

Host-key verification and reconnect state belong to Battleground rather than the user's shell configuration, and the desktop should use an embedded SSH implementation so macOS, Windows, and Linux behavior does not depend on `ssh`, `rsync`, WSL, or shell quoting. RFC 4254 explicitly supports multiple command/data channels in one connection, but SFTP is not guaranteed by that base protocol; probe it and retain tar/archive-over-command as a fallback. [`SSH channel and exec semantics`](https://datatracker.ietf.org/doc/html/rfc4254), [`OpenSSH host-key and liveness options`](https://man.openbsd.org/OpenBSD-current/man/ssh_config)

## Provider-agnostic V1 contract

The provider adapter should return capabilities and consequences, not force every provider into a fake `start/stop` vocabulary:

```text
discoverLocations()
discoverComputeOptions() -> GPU, architecture, price, stock, capability set
prepareAccess(appPublicKey)
prepareStorage(storageIntent)
provision(spec) -> stable provider resource ID
reconcile(resourceID) -> normalized state + fresh SSH endpoint
pause(resourceID, supportedPolicy)
release(resourceID, storagePolicy)
costSnapshot(resourceID)
```

At minimum, each compute option/resource reports:

```text
bootstrap: template | cloud_init | startup_script | ssh_only
ssh: proxied_exec | direct_tcp
file_transfer: sftp | archive_over_exec | unavailable
pause: stop_unbilled | hibernate_partial | stop_billed | recreate_only | unavailable
resume: same_resource_capacity_dependent | recreate_from_storage | user_managed
storage: resource_bound | datacenter_bound | region_bound | unknown
cost: provider_reconciled | local_estimate | unknown
```

All provider mutations are persisted as intended operations before the request and reconciled by stable provider ID after timeout or desktop restart. The UI always previews data-loss, billing, storage, and capacity consequences before pause/release. Provider API credentials and SSH private keys stay in the operating-system credential vault and never enter the Research Project or the remote scratch workspace.

The SSH runner owns a sequence-numbered durable event/log spool and continues independently of an individual SSH channel. Battleground imports it incrementally into the local Experiment Ledger. Before any destructive compute release, it stops or quiesces the runner, imports through the final sequence, verifies the durable copy, applies the selected storage policy, then releases compute. A changed GPU, driver/CUDA stack, architecture, or other material environment after recovery creates a new execution-environment segment rather than silently comparing unlike Experiment results.

## Remaining validation before implementation freeze

Documentation is sufficient to choose the architecture, but not to certify real-world behavior. Before freezing the adapters, run the same cheapest-safe smoke test on all three native providers:

1. create through REST with an app-owned SSH key and bootstrap;
2. verify direct SSH, exec, SFTP/archive fallback, GPU detection, and no-sudo runner install;
3. disconnect/reconnect and resume the event spool;
4. exercise the advertised billing-ending lifecycle while retaining selected data;
5. recreate/restore and verify connection-detail rediscovery and data integrity;
6. reconcile actual charges against the API/console; and
7. specifically determine whether Verda's `hibernate` currently deletes the instance and retains volumes, as its OpenAPI says, or supports same-instance resume, as its CLI page claims.

That smoke test should be a later validation task, not an unresolved architecture decision. The V1 contract above remains correct under either Verda outcome because lifecycle is capability-driven.

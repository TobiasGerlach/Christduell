# First deployment to Azure — step by step

Written for someone who has not used Terraform before. Nothing here has been run yet:
`infra/` has no state file and `container_image` still contains the `XXXXXX` placeholder, so
**Azure is currently empty**. This is a from-scratch setup.

Budget half a day. Expect one step to fail on something dumb (a name collision, a missing
permission) — that is normal, not a sign you did it wrong.

---

## The mental model

Two separate tools that both talk to your Azure account:

```
  infra/  (Terraform)                 .github/workflows/  (GitHub Actions)
  "create the empty machines"         "put my code on them"
  run once, then on infra changes     run on every release
```

Terraform builds the house. The deploy pipeline moves the furniture in. Terraform never
touches your Python code; the pipeline never creates servers.

### Terraform in four sentences

The `.tf` files describe **what should exist** in Azure. `terraform plan` shows what it would
change without changing anything; `terraform apply` makes Azure match the description. It
records what it created in a **state file** — lose that and Terraform forgets it owns your
infrastructure and tries to build a second copy of everything. You never click around in the
Azure portal, because the portal and the `.tf` files would drift apart.

### What gets created

| Resource | In plain terms | Rough cost |
|---|---|---|
| Resource group | A folder holding everything else | free |
| Container Registry (ACR) | Your private Docker Hub | ~5 €/mo |
| App Service Plan | The rented VM | ~13 €/mo (B1) |
| Linux Web App | Runs your container on that VM | included |
| Notification Hub | Provisioned but unused — push goes via Expo | free tier |
| `/home` file share | Persistent disk holding `christduell.db` | pennies |

Roughly **20 €/month**. Deleting the resource group deletes all of it.

---

## Step 0 — prerequisites

```sh
az login                    # Azure CLI, opens a browser
az account show             # confirm you landed in the right subscription
terraform version           # needs >= 1.13
docker version              # daemon must be running for step 4
```

---

## Step 1 — somewhere safe for the state file

The state file records what Terraform built. By default it lands on your laptop, which is bad
for two reasons: losing the laptop means losing track of your infrastructure, and the file now
also contains the **JWT signing key** Terraform generates for the API.

Create a storage account for it (one-off):

```sh
az group create -n christduell-tfstate-rg -l westeurope
az storage account create -n christduelltfstate -g christduell-tfstate-rg \
    -l westeurope --sku Standard_LRS
az storage container create -n tfstate --account-name christduelltfstate
```

> `christduelltfstate` has to be globally unique across all of Azure. If it is taken, add a
> suffix and use the same name in the next step.

Then uncomment the `backend "azurerm"` block in `infra/providers.tf` and make the names match.

---

## Step 2 — configure

```sh
cd infra
cp terraform.tfvars.example terraform.tfvars   # gitignored, never commit it
```

Edit `terraform.tfvars`:

```hcl
container_image = "nginx:latest"   # see below
cors_origins    = ""               # fill in once the web build has a URL
billing_provider = "none"          # Stripe comes later
push_enabled     = false           # needs an EAS project id first
```

**Why `nginx:latest`?** Chicken and egg: the Web App needs an image to run, but your registry
does not exist yet and holds nothing. So the first apply boots a placeholder, and step 5
replaces it with your real backend. It is meant to look wrong at first.

---

## Step 3 — build it

```sh
terraform init      # picks up the new remote-state backend
terraform plan      # READ THIS. It changes nothing.
terraform apply     # type "yes"
```

`plan` output: `+` creates, `~` changes, `-` destroys. On a first run everything is `+` and
nothing should say `destroy`.

Then collect what you need next:

```sh
terraform output                                   # app URL, registry address
terraform output -raw jwt_secret_key               # generated for you; keep it secret
az acr credential show --name <acr-name> --query "{user:username, pass:passwords[0].value}"
```

The app is live but running nginx. That is expected.

---

## Step 4 — check the image builds

The container applies database migrations on boot, so it must contain `alembic.ini` and
`migrations/`. Build it once locally before trusting the pipeline:

```sh
cd backend
docker build -t christduell-backend:test .
docker run --rm -p 8000:8000 -e ENVIRONMENT=local christduell-backend:test
curl localhost:8000/health     # {"status":"ok"}
```

If the log says `Path doesn't exist: /app/migrations`, the Dockerfile lost its `COPY` lines.

---

## Step 5 — wire up GitHub and deploy

In GitHub → Settings → Secrets and variables → Actions, add five repository secrets:

| Secret | Where it comes from |
|---|---|
| `ACR_LOGIN_SERVER` | `terraform output container_registry_login_server` |
| `ACR_USERNAME` | the `az acr credential show` output above |
| `ACR_PASSWORD` | same |
| `AZURE_WEBAPP_NAME` | `<project>-<environment>-api`, e.g. `christduell-production-api` |
| `AZURE_CREDENTIALS` | the command below |

```sh
az ad sp create-for-rbac --name christduell-deploy --role contributor \
  --scopes "$(az group show -n christduell-production-rg --query id -o tsv)" \
  --sdk-auth
```

Paste the whole JSON block, braces included, as `AZURE_CREDENTIALS`.

Then: GitHub → **Actions** → **Backend Deploy (Azure)** → **Run workflow**. It builds the
image, pushes it to your registry and points the Web App at it. Takes a few minutes.

Afterwards set `container_image` in `terraform.tfvars` to the real address
(`<acr>.azurecr.io/christduell-backend:latest`) so it is accurate — Terraform will not fight
the pipeline over it, the running image is under `ignore_changes`.

---

## Step 6 — prove it works

```sh
curl https://<app>.azurewebsites.net/health
BASE_URL=https://<app>.azurewebsites.net make smoke
```

The smoke test registers two throwaway accounts, plays a complete eight-round duel, walks the
research and billing flows, then deletes the accounts. 29 checks. If they pass, the deployment
is genuinely working — not just responding.

Then load the questions into the production database:

```sh
az webapp ssh --resource-group christduell-production-rg --name <app>
python -m app.db.seed
```

> `app.db.seed` also creates the two demo players (`anna@` / `tobias@christduell.test`) with a
> known password. Delete them in production, or edit `SEED_PLAYERS` first.

---

## When something breaks

```sh
az webapp log tail --resource-group christduell-production-rg --name <app>
```

| Symptom | Usual cause |
|---|---|
| Container never starts | Missing `alembic.ini`/`migrations/` in the image (step 4) |
| `RuntimeError: Refusing to start` | `SECRET_KEY` or `BILLING_PROVIDER` misconfigured — the app blocks unsafe production settings on purpose |
| App responds, browser blocked | `cors_origins` does not match the web build's origin exactly (scheme + host + port) |
| 502 for the first ~2 minutes | Normal cold start after a deploy |
| ACR push denied | `admin_enabled` off, or the wrong `ACR_PASSWORD` |

Rolling back is redeploying the previous image tag — every build is tagged with its git commit,
so pick the older tag in the Web App's Deployment Center.

---

## After the first deploy

- [ ] Custom domain + certificate (`*.azurewebsites.net` is fine for a beta, not a launch)
- [ ] Schedule `scripts/backup-db.sh` — the SQLite file has no managed backup behind it
- [ ] Schedule `make maintenance` daily (downgrades lapsed subscriptions)
- [ ] Add uptime monitoring against `/health`
- [ ] Only then: Stripe (`billing_provider = "stripe"`) and push (`push_enabled = true`)

Two things deliberately left alone for now, both listed in `todos.md`:

- **Deploy is manual, not on push.** Keep it that way until a few deploys have gone smoothly.
- **GitHub stores an ACR password that never expires.** Azure OIDC federated credentials would
  remove it. Worth doing eventually, not before launch.

## If a database already exists

Not your case today — a fresh deployment creates and migrates its database on first boot with
no action from you. But if you ever restore a `christduell.db` that predates Alembic, tell
Alembic where it stands before upgrading, or it will try to create tables that are already
there:

```sh
alembic stamp 0001 && alembic upgrade head
```

Back it up first with `scripts/backup-db.sh`.

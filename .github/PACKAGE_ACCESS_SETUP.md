# Fixing 403 Forbidden Error for GHCR

If you're getting `403 Forbidden` when pushing to `ghcr.io`, follow these steps:

## Step 1: Check Repository Workflow Permissions

1. Go to: https://github.com/HyperbolicLabs/inference-benchmarks/settings/actions
2. Scroll to **Workflow permissions**
3. Ensure **Read and write permissions** is selected (not "Read repository contents and packages permissions")
4. Save changes

## Step 2: Grant Package Access (After First Push)

Once the package is created (even if the first push fails), you need to grant access:

1. Go to: https://github.com/orgs/HyperbolicLabs/packages
2. Find the package: `ghcr.io/hyperboliclabs/aiperf` or `ghcr.io/hyperboliclabs/osworld`
3. Click on the package
4. Go to **Package settings** (right sidebar)
5. Scroll to **Manage Actions access**
6. Click **Add repository**
7. Search for: `HyperbolicLabs/inference-benchmarks`
8. Set role to: **Write**
9. Click **Add repository**

## Step 3: Check Organization Settings

1. Go to: https://github.com/orgs/HyperbolicLabs/settings/packages
2. Ensure **Package creation** is enabled
3. Check **Package access** settings

## Alternative: Use Personal Access Token (if org settings block it)

If organization settings prevent package creation, you may need to:
1. Create a Personal Access Token (PAT) with `write:packages` scope
2. Add it as a repository secret: `GHCR_TOKEN`
3. Update workflow to use `${{ secrets.GHCR_TOKEN }}` instead of `${{ secrets.GITHUB_TOKEN }}`

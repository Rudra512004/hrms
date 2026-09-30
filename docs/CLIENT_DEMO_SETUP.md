# Client Demo Setup

Before sharing the HRMS URL, configure the backend's real SMTP credentials in Render:

- `EMAIL_HOST`, `EMAIL_PORT`, `EMAIL_USE_TLS`, `EMAIL_HOST_USER`, `EMAIL_HOST_PASSWORD`, and `DEFAULT_FROM_EMAIL`.

These values deliver account-verification and employee-invitation links to real inboxes. Never commit them. `DEMO_SUPERADMIN_*` is optional and reserved for BeyondSure platform operations; clients do not need it.

## Client self-service flow

1. A client opens **Create your HRMS workspace** from the login page and enters their own business email and name.
2. The client receives a verification email, opens it, and chooses a password.
3. After signing in, the client opens **Organization Launchpad** and creates exactly one organization and its first branch.
4. The platform creates an organization-scoped **Organization Owner** role for that verified account. It is not a global Super Admin and has no Employee record or employee self-service access.
5. The Owner configures the organization, creates dynamic roles, chooses permissions, and invites employees.
6. Each employee receives an activation email at the invitation email, or the work email when an invitation email is not supplied. After activation, their navigation and APIs are limited to their Employee relationship and assigned dynamic role permissions.

Each client Owner is server-side scoped to only their organization. They cannot list, retrieve, modify, create resources for, or assign roles across another client organization.

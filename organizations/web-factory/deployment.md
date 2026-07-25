# Delivery boundary

Web Factory currently builds and validates sites locally. It does not create
remote repositories, push branches, configure DNS, or deploy to production.

Maintenance intake and project archival are deliberately outside this test
scope, so the `maintenance-intake` and `project-archive` workflows are not
shipped. Restore them only when that lifecycle is explicitly approved.

The review artifact is the selected theme's clean `dist/`, produced with:

```bash
npm run verify
```

`npm run preview:all` is an internal multi-theme draft and is never the delivery
artifact.

Future repository provisioning will create one Bitbucket repository per hotel.
That automation must remain outside the authoring pipeline until its credentials,
ownership, rollback and approval model are specified.

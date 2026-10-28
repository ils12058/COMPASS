# Identity and normalization

Implementation: `be/compass/good_moral/receipt_identity.py`, with an equivalent frozen `gm_or_key(text)` SQL function in migration `0002_receipt_identity_and_history`.

`GM_OR_V1` requires text and rejects every character outside printable ASCII U+0020–U+007E **before trimming**. It trims ordinary outer spaces, rejects an empty result and display values longer than 96 characters, and uppercases ASCII for the identity key. The trimmed original case remains the display. `None` or ordinary space-only text in the correction wrapper means deliberate absence; the normalization function itself never reserves an empty number.

| Input | Display | Key |
| --- | --- | --- |
| `  or-00042  ` | `or-00042` | `OR-00042` |
| `OR00042` | unchanged | `OR00042` |
| `OR-42` | unchanged | `OR-42` |
| `OR  00042` | two internal spaces retained | `OR  00042` |
| `pre/00042.A` | unchanged | `PRE/00042.A` |
| Tab/newline/DEL/NUL, full-width digits, en dash, bidi/zero-width characters | rejected for new entry | no reservation |

Prefixes, hyphens, slashes, punctuation, internal spaces and leading zeroes remain significant. No integer parsing, punctuation stripping, Unicode repair or internal whitespace collapse occurs. The canonical key column uses PostgreSQL `C` collation; named uniqueness is global across F4/F6, Students, academic years and every lifecycle status. The version is constrained to GM_OR_V1 and is **not** another uniqueness namespace.

The database also verifies canonical key spelling and identity/claim display correspondence. Application preflight is not the conflict authority: competing inserts are arbitrated by `gm_receipt_identity_key_uniq`. Only that named violation becomes the safe receipt-conflict response.

Once reserved, an identity cannot be rekeyed, rebound or deleted through ordinary ORM/SQL operations. An ordinary reservation must have an immutable claim by commit. Clearing, replacing or cancelling does not free it. A previously superseded number cannot be reactivated even by its former request. Same-number date/amount corrections revise its facts under the existing binding.

**Institutional assumption, not policy approval:** this grammar and case equivalence are implemented for synthetic testing as requested. Cashier must confirm whether printed series/book/office prefixes are essential to global identity. If books repeat a bare numeric sequence, revise the approved full printed identity scope before operational activation; do not invent Student/year scoping. Unsupported legacy characters are preserved as quarantined observations, never silently normalized or assigned invented aliases. Their unresolved collision risk blocks the provided activation check.

These guards protect ordinary application/database writes, not a privileged database owner deliberately disabling triggers, dropping/truncating tables, or restoring an incomplete backup. Operational access and backup-gap reconciliation remain required.

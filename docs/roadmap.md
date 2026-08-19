# Accountant roadmap

Feature plan for both repositories, kept in the backend repo so every session
starts from the same list. Status is verified against the code, not against
intent: `done` means the endpoint or screen exists and is reachable.

Frontend work lives in the separate `accountant-frontend` repository and is
released together with the matching backend commit.

## 1. Dashboard analytics

- [x] Change against the previous month
- [x] Monthly spending average
- [x] Highest spending category
- [x] Upcoming payments on the overview
- [x] Monthly income and expense chart
- [x] Past month selection

The overview walks month by month and names the month it is showing. Only the
month list follows the picker: the balance, the six-month average and the
budget screen stay anchored to the running month, so stepping back to read
history cannot make today's figures look wrong.

## 2. Savings

- [x] Store the money left at the end of a month
- [x] Automatic monthly close — `POST /savings/process-month-end` catches up
      every month since the account was created
- [x] Total savings
- [x] Monthly savings history
- [x] Savings screen

## 3. Transaction management

- [x] Separate screen listing every transaction
- [x] Date, category and kind filters
- [x] Editing a transaction
- [x] Deleting a transaction
- [x] Opening balance

`GET /transactions` accepts optional `category_id` and `kind` filters next to
its required range, `PATCH` and `DELETE /transactions/{id}` edit and remove a
single record, and `PUT /balance/opening` stores the signed opening balance on
the user. The opening balance is added to the current balance wherever it is
shown, including the administration summary, and is left out of monthly cash
flow so it never counts as income in a savings month.

## 4. Recurring transactions

- [x] Recurring income such as a salary
- [x] Processing recurring charges in the background, without the app being
      opened
- [x] Editing a recurring entry's name, category, amount and billing day

An entry's kind comes from its category, so no column or migration was needed
and re-pointing an entry at an income category turns its future charges into
income. A scheduler in the application sweeps every active user hourly and on
start, next to the existing `POST /subscriptions/process-due` the frontend
calls for an immediate result; both go through the same idempotent path.
`PATCH /subscriptions/{id}` replaced the price-only endpoint.

## 5. Administration

- [x] User list
- [x] Viewing a user's finance data
- [x] Deactivating a user
- [ ] Administrator action history
- Role assignment — dropped on purpose, see below

Roles are granted directly in the database. The panel used to hand out the
`ADMIN` role and that was removed: an administrator can no longer promote
anyone, so the only way in is a row in `user_roles`. What is left of account
management is switching a user active or inactive, and an administrator still
cannot deactivate their own account.

## 6. Enabling mail

Delivery code and per-user send times are done. Connecting a real Gmail account
is an operations step: it needs a Gmail address and a Google App Password in
`.env`, never the account's normal password. See the README.

## 7. Hardening

- [x] Password change
- [ ] Password reset — needs a connected Gmail account, see phase 6
- [ ] Email change
- [ ] HTTPS and production setup
- [ ] Backups and error logs
- [ ] Mobile and visual pass

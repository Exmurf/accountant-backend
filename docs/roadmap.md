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
- [ ] Past month selection — the overview is fixed to the current month

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

- [ ] Recurring income such as a salary — subscriptions reject non-expense
      categories today
- [ ] Processing subscriptions in the background, without the app being opened;
      due charges are currently posted by `POST /subscriptions/process-due`,
      which the frontend calls
- [ ] Editing a subscription's name, category and billing day — only
      `PATCH /subscriptions/{id}/price` exists

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

- [ ] Password change and reset
- [ ] Email change
- [ ] HTTPS and production setup
- [ ] Backups and error logs
- [ ] Mobile and visual pass

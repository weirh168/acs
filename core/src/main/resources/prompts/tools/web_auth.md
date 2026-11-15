Check whether the page you have open is a sign-in wall, before you spend steps reading or clicking a page that is only a login prompt.

It looks for the three usual giveaways: a password field, a form that posts to a login path, and login wording in the text or the URL. One sign is suspicious, two or more means `needsLogin: true`. You get the site `host` and the `signals` that fired, so you can say why.

When it says `needsLogin: true`, do not type credentials yourself and do not try to work around the wall. Ask the user to sign in: call `mika_login_site` with the reported host, wait for them, then `mika_confirm_login` to record it, and continue with the page.

When it says false, the page is readable as-is. It only reads the current tab and never fills or submits anything.

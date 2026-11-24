# Static deployment

The public demo uses Cloudflare Pages Direct Upload in the dedicated `healthcare-payment-integrity` project. It serves the v1.0.1 static workspace from the default Pages domain. [Live demo](https://healthcare-payment-integrity.pages.dev/)

`release/static` is the only hosting input. It contains the entry point, aggregate study JSON, bundled JavaScript and CSS, security headers, license notices and a 404 page. The research lab and fictional review exercise run inside the browser. The app uses hash paths so deep views work from the index. A top-level 404 makes missing files return an error. The local static verification server applies the same header values. Export writes build fingerprints to `release/static-build-manifest.json`. The release attestation binds those files and verification evidence to the tagged commit. [Cloudflare Pages routing](https://developers.cloudflare.com/pages/configuration/serving-pages/) · [Pages headers](https://developers.cloudflare.com/pages/configuration/headers/)

Cloudflare's documentation reviewed November 24, 2026 describes free, unlimited requests for assets that do not invoke a function. The export has zero Functions or Worker code. No storage bindings, AI services, metered compute, paid domain or API have been configured for this project. Pricing and account constraints should be rechecked for any authorized deployment. [Pages pricing](https://developers.cloudflare.com/pages/functions/pricing/) · [Pages limits](https://developers.cloudflare.com/pages/platform/limits/)

For an authorized update, verify the Wrangler identity and target account before using Direct Upload. [Cloudflare Direct Upload](https://developers.cloudflare.com/pages/get-started/direct-upload/)

1. Build and verify the static export using the release commit. Check each local file against the release manifest and select only the `release/static` directory.
2. In **Workers & Pages**, choose **Create application**, **Get started**, then **Drag and drop your files**. Enter the authorized project name and select the audited directory. Use the included `_headers` and `404.html` as the hosting configuration.
3. Use the supplied `pages.dev` address with the static file service. Keep Functions and bindings disabled. Direct Upload serves the seven prebuilt files without a hosted build or custom domain.
4. At the authorized deployment URL, check the index, planner and review hash routes, missing asset status, CSP and same-origin asset requests. Compare response bytes to the audited build.

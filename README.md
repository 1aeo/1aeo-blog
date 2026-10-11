# 1AEO blog

Source of truth for [1aeo.com/blog](https://1aeo.com/blog/): every published post, its images, the code that builds posts, and scripts that reproduce the charts from Tor's public data.

## Layout

| Path | What it is |
|---|---|
| `site/blog/` | The deployable blog: published posts, `index.html` and `images/`. Mirrors `/blog/` on the server. |
| `site/sitemap.xml` | The site's sitemap. Add every new post here. |
| `src/<post-slug>/` | Builders for posts written as code (`build.py` writes `site/blog/<post-slug>.html`) and the post's blog-index entry. |
| `templates/` | House style: the shared `<style>` block and nav. |
| `charts/<post-slug>/` | Scripts that reproduce a post's charts from public data (CollecTor, Onionoo). Each folder has its own README. |
| `tools/deploy.sh` | Deploys `site/` to the server: a dry run by default, `--apply` to copy. |

## Publishing a post

1. Draft in `drafts/` (git-ignored). **Nothing unpublished is ever committed: this repo is public.**
2. Once approved, write the final HTML to `site/blog/`, or move its builder to `src/<post-slug>/` and run it. Put images in `site/blog/images/`.
3. Add the post to `site/blog/index.html` (newest first, `post-preview` block) and to `site/sitemap.xml`.
4. Commit, then run `tools/deploy.sh` to review the dry run and `tools/deploy.sh --apply` to publish.
5. Check the live page and its links.

## Rules for this public repo

- No drafts, no first-party relay telemetry, no credentials, no server addresses.
- Charts in `charts/` must rebuild from public data alone.
- Cloudflare's Email Obfuscation rewrites anything that looks like `user@host`, commands included. Wrap post content in `<!--email_off-->` … `<!--/email_off-->`.

## License

Code (`charts/`, `src/`, `tools/`) is under the Apache License 2.0 (see `LICENSE`). Blog posts and images © 1AEO.

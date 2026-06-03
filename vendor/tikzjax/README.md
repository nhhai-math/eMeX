TikZJax runtime vendored for eMeX preview.

Source:
- https://tikzjax.com/v1/tikzjax.js
- https://tikzjax.com/v1/fonts.css
- https://s3.us-east-2.amazonaws.com/tikzjax.com/3f69afb974a1e83f66a36f7618f88a38c254034b.wasm
- https://s3.us-east-2.amazonaws.com/tikzjax.com/b565ab0b474e8e557d954694b7379a57db669ac9.gz
- https://tikzjax.com/bakoma/ttf/

Local patch:
- v1/tikzjax.js resolves its WASM and gzipped core from the current script URL
  instead of the upstream S3 base URL.

License:
- See LICENSE.md from kisonecat/tikzjax.

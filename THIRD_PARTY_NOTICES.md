# Third-party notices

The Overleaf web protocol handling in `src/` (cookie plus CSRF session bootstrap, the project socket, joining
documents over a hand-written Socket.IO 0.9 long-polling client, reading comment ranges and tracked changes, the
comment thread endpoints) follows the approach worked out in **olcli** by Alexander Loth,
https://github.com/aloth/olcli, which is distributed under the MIT License:

```
MIT License

Copyright (c) 2026 Alexander Loth

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
```

This package is a separate implementation in plain JavaScript without dependencies, not a copy of olcli's
TypeScript, and it adds writing tracked changes, which olcli does not do.

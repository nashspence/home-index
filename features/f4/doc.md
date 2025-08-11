# f4 docs

## overview
Modules run on [*deriver host*](../glossary.md#deriver-host) via
[*queue host*](../glossary.md#queue-host).
Archive drives from [f3](../f3.md) queue before regular files.

## modules
Each module lists a name and uid.
Changing the list or a uid requeues files from that point.
Modules remain forward compatible.

## tokens
`RESOURCE_SHARES` declare scarce resources.
Jobs start only when holding all required tokens.

## return contract
Modules return
`"document"` to merge into [*doc*](../glossary.md#doc)
and optional `"content"` for [f5](../f5.md).

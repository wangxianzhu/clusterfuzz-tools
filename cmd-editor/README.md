Command-line Editor
======================

Enable user to edit content within your command-line tool.


Usage
--------

```
from cmd_editor import editor

print editor.edit(
    'Test content', prefix='my-app-', editor_env='CMD_EDITOR',
    default_editor='vim')
```

An editor will be opened with 'Test content'. After user edits and saves,
the edited content is returned from `editor.edit()`.


Publish
---------

TBD

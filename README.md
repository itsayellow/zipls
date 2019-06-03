# zipls
ls inside of a zip file (without extracting!)

zipls will produce near-identical output on a zip file as ls would after extracting the zip file into the current directory.

Some of the key ls switches are replicated.
## Installation

     pipx install --spec git+https://github.com/itsayellow/zipls zipls 

## Examples
(myzipfile.zip has top-level internal directory of 'topleveldir'):
    
    zipls myzipfile.zip

    zipls myzipfile.zip topleveldir

    zipls myzipfile.zip 'topleveldir/*'

    zipls --color myzipfile.zip 'topleveldir/*'

    zipls -F myzipfile.zip 'topleveldir/*'

    zipls -l myzipfile.zip 'topleveldir/*'
    zipls -lh myzipfile.zip 'topleveldir/*'
    
    zipls -d myzipfile.zip 'topleveldir/*'

    zipls -a myzipfile.zip 'topleveldir/*'

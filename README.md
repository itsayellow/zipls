# zipls
ls inside of a zip file (without extracting!)

zipls will produce near-identical output on a zip file as ls would after extracting the zip file in the current directory.

Some of the key ls switches are replicated.

Examples (myzipfile.zip has top-level internal directory of 'topleveldir'):
    
    zipls myzipfile.zip

    zipls myzipfile.zip topleveldir

    zipls myzipfile.zip 'topleveldir/*'

    zipls --color myzipfile.zip 'topleveldir/*'

    zipls -F myzipfile.zip 'topleveldir/*'

    zipls -l myzipfile.zip 'topleveldir/*'

    zipls -d myzipfile.zip 'topleveldir/*'

    zipls -a myzipfile.zip 'topleveldir/*'

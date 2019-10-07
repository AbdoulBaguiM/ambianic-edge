
# exit on error, verbose mode
set -ex

# script's own dir
MY_DIR="$(dirname "$0")"
cd $MY_DIR/../
echo PWD=$PWD
WORKDIR=$PWD
pip3 install mkdocs
pip3  install pydoc-markdown
cp src/ambianic/webapp/client/public/favicon.ico $WORKDIR/docs/
cd src
pydocmd simple ambianic++ ambianic.pipeline++ ambianic.pipeline.ai++ \
  ambianic.pipeline.avsource++ ambianic.webapp++ > "$WORKDIR/docs/ambianic-python-api.md"
mkdocs build -f "$WORKDIR/docs/mkdocs.yml"

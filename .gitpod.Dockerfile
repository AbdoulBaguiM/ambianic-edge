# FROM ambianic/ambianic-edge:dev
# Starting from the ambianic dev image results in errors when gitpod tries to build a workspace. Gitpod error below:
# build failed: cannot build base image: failed to register layer: Error processing tar file(exit status 1): Container ID 306111 cannot be mapped to a host ID5f5935479edd: Download complete

FROM gitpod/workspace-full

# The docker image build context doesn't seem to be able to access this repo files...
# Workaround is to pull the latest script version from the repo, which can lead to confusion,
# because it is not the same version as the script in the branch where this dockerfile comes from

# install wget
# RUN sudo apt-get install -y curl && \
#  curl -k -L -o ./install_requirements.sh https://raw.githubusercontent.com/ambianic/ambianic-edge/master/build/install_requirements.sh && \
#  sudo /bin/bash ./install_requirements.sh
  
# Install custom tools, runtimes, etc.
# For example "bastet", a command-line tetris clone:
# RUN brew install bastet
#
# More information: https://www.gitpod.io/docs/config-docker/


# Disable pyenv, which gitpod installs by default
# but it doesn't play well with system level dependencies like gstreamer python wrappers and tflite
# comment out lines in init shell script that enable pyenv
RUN sudo sed -i '/pyenv /s/^/#/' /home/gitpod/.bashrc.d/60-python

# Copy dependencies install list and script
# COPY install_requirements.sh install_requirements.sh
COPY ["./build/*", "./"]
RUN arch && ls -al && sudo /bin/bash ./install_requirements.sh

# install gtipod environment dev packages for app testing
RUN   python3 -m pip install --upgrade pip && \
      pip3 install -U pytest && \
      pip3 install -U codecov && \
      pip3 install -U pytest-cov && \
      pip3 install -U pylint && \
      sudo ln -s /usr/bin/python3 /usr/bin/python
      

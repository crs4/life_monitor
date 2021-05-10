#!/bin/bash

# set target
target_path="../dist/plugins"

# clean
rm -Rf ${target_path}
mkdir -p ${target_path}

# bootstrap
cp -r node_modules/bootstrap/dist "${target_path}/bootstrap"

# jquery
cp -r node_modules/jquery/dist "${target_path}/jquery"

# fortawesome
cp -r node_modules/@fortawesome/fontawesome-free "${target_path}/fontawesome-free"

# sweetalert2-theme-bootstrap-4
cp -r node_modules/@sweetalert2/theme-bootstrap-4 "${target_path}/sweetalert2-theme-bootstrap-4"

# sweetalert2
cp -r node_modules/sweetalert2/dist/ "${target_path}/sweetalert2"

# toastr
cp -r node_modules/toastr/build/ "${target_path}/toastr"

# tempusdominus-bootstrap-4
cp -r node_modules/tempusdominus-bootstrap-4/build "${target_path}/tempusdominus-bootstrap-4"

# icheck-bootstrap
cp -r node_modules/icheck-bootstrap "${target_path}/icheck-bootstrap"

# select2
cp -r node_modules/select2/dist "${target_path}/select2"
cp -r node_modules/select2-bootstrap4-theme/dist "${target_path}/select2-bootstrap4-theme"

# duallist
cp -r node_modules/bootstrap4-duallistbox/dist "${target_path}/bootstrap4-duallistbox"

# bootstrap-switch
cp -r node_modules/bootstrap-switch/dist "${target_path}/bootstrap-switch"

# bootstrap-switch-button
cp -r node_modules/bootstrap-switch-button "${target_path}/bootstrap-switch-button"

# jqvmap-novulnerability
cp -r node_modules/jqvmap-novulnerability/dist "${target_path}/jqvmap-novulnerability"

# overlayScrollbars
cp -r node_modules/overlayscrollbars "${target_path}/overlayscrollbars"

# summernote
cp -r node_modules/summernote/dist "${target_path}/summernote"

# dropzone
cp -r node_modules/dropzone/dist "${target_path}/dropzone"
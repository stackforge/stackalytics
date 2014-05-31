# -*- mode: ruby -*-
# vi: set ft=ruby :

VAGRANTFILE_API_VERSION = "2"

Vagrant.configure(VAGRANTFILE_API_VERSION) do |config|
  config.vm.box = "centos65x64"
  config.vm.box_url = "http://opscode-vm-bento.s3.amazonaws.com/vagrant/virtualbox/opscode_centos-6.5_chef-provisionerless.box"
  config.vm.network "forwarded_port", guest: 80, host: 8080
  config.vm.synced_folder ".", "/opt/stack/stackalytics"
  config.vm.synced_folder "puppet/templates", "/tmp/vagrant-puppet/templates"
  config.vm.synced_folder "puppet/files", "/etc/puppet/files"
  config.vm.provider "virtualbox" do |vb|
    vb.cpus = 2
    vb.memory = 4096
  end
  config.vm.provision "shell", path: "puppet/scripts/bootstrap.sh"
  config.vm.provision "puppet" do |puppet|
    puppet.manifests_path = "puppet"
    puppet.manifest_file  = "manifests/init.pp"
    puppet.options = ["--templatedir","/tmp/vagrant-puppet/templates","--fileserverconfig","/vagrant/fileserver.conf"]
   end
end

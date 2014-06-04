require 'beaker-rspec'

unless ENV['RS_PROVISION'] == 'no'
  hosts.each do |host|
    # Install Puppet
    if host.is_pe?
      install_pe
    else
      install_puppet
    end
  end
end

RSpec.configure do |c|
  # Project root
  proj_root = File.expand_path(File.join(File.dirname(__FILE__), '..'))

  # Readable test descriptions
  c.formatter = :documentation

  # Configure all nodes in nodeset
  c.before :suite do
    # Install module and dependencies
    puppet_module_install(:source => proj_root, :module_name => 'vcsrepo')
    hosts.each do |host|
      case fact('osfamily')
      when 'RedHat'
        install_package(host, 'git')
      when 'Debian'
        install_package(host, 'git-core')
      else
        if !check_for_package(host, 'git')
          puts "Git package is required for this module"
          exit
        end
      end
      shell('git config --global user.email "root@localhost"')
      shell('git config --global user.name "root"')
    end
  end
end

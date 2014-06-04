test_name 'C3472 - create bare repo that already exists'

# Globals
repo_name = 'testrepo_bare_repo_already_exists.git'

hosts.each do |host|
  tmpdir = host.tmpdir('vcsrepo')
  step 'setup - create bare repo' do
    install_package(host, 'git')
    on(host, "mkdir #{tmpdir}/#{repo_name}")
    on(host, "cd #{tmpdir}/#{repo_name} && git --bare init")
  end

  teardown do
    on(host, "rm -fr #{tmpdir}")
  end

  step 'create bare repo that already exists using puppet' do
    pp = <<-EOS
    vcsrepo { "#{tmpdir}/#{repo_name}":
      ensure => bare,
      provider => git,
    }
    EOS

    apply_manifest_on(host, pp, :catch_failures => true)
    apply_manifest_on(host, pp, :catch_changes  => true)
  end

  step 'verify repo does not contain .git directory' do
    on(host, "ls -al #{tmpdir}/#{repo_name}") do |res|
      fail_test "found .git for #{repo_name}" if res.stdout.include? ".git"
    end
  end

end

# Spectrometer
class spectrometer (
    $clone_repo                 = $spectrometer::params::clone_repo,
    $git_repo_uri               = $spectrometer::params::git_repo_uri,
    $user                       = $spectrometer::params::user,
    $group                      = $spectrometer::params::group,
    $config_dir                 = $spectrometer::params::config_dir,
    $config_file                = $spectrometer::params::config_file,
    $uwsgi_config_file          = $spectrometer::params::uwsgi_config_file,
    $log_dir                    = $spectrometer::params::log_dir,
    $log_file                   = $spectrometer::params::log_file,
    $install_dir                = $spectrometer::params::install_dir,
    $sources_root               = $spectrometer::params::sources_root,
    $processor_hour             = $spectrometer::params::processor_hour,
    $processor_minute           = $spectrometer::params::processor_minute,
    $processor_log_file         = $spectrometer::params::processor_log_file,
    $ssh_username               = $spectrometer::params::ssh_username,
    $ssh_key_filename           = $spectrometer::params::ssh_key_filename,
    $uwsgi_port                 = $spectrometer::params::uwsgi_port,
    $uwsgi_pid_file             = $spectrometer::params::uwsgi_pid_file,
    $default_data_uri           = $spectrometer::params::default_data_uri,
    $runtime_storage_uri        = $spectrometer::params::runtime_storage_uri,
    $listen_host                = $spectrometer::params::listen_host,
    $listen_port                = $spectrometer::params::listen_port,
    $corrections_uri            = $spectrometer::params::corrections_uri,
    $review_uri                 = $spectrometer::params::review_uri,
    $force_update               = $spectrometer::params::force_update,
    $programs_uri               = $spectrometer::params::programs_uri,
    $default_metric             = $spectrometer::params::default_metric,
    $default_release            = $spectrometer::params::default_release,
    $default_project_type       = $spectrometer::params::default_project_type,
    $dashboard_update_interval  = $spectrometer::params::dashboard_update_interval
) inherits spectrometer::params {

    class {'epel':}

    if $clone_repo == true {
        vcsrepo { $install_dir:
            ensure   => present,
            provider => git,
            source   => $git_repo_uri,
        }
    }

    exec { 'Install Development Tools':
      unless  => 'yum grouplist "Development tools" | grep "^Installed Groups"',
      command => 'yum -y groupinstall "Development tools"',
      path    => $::path
    }

    $deps = [ 'python',
              'python-devel',
              'python-setuptools',
              'git',
              'memcached',
              'nginx'
    ]

    package { $deps:
        ensure   => installed,
        require  => Class['epel']
    }

    exec { 'Install pip':
        unless   => 'which pip',
        command  => 'easy_install pip',
        path     => $::path,
        user     => root,
        require  => Package['python-setuptools']
    }

    exec { 'Install uwsgi':
        unless  => 'which uwsgi',
        command => 'pip install uwsgi',
        path    => $::path,
        user    => root,
        require => [Package['python-setuptools'],
                    Exec['Install pip']
        ]
    }

    exec { 'Install Spectrometer':
        unless      => 'pip list | grep stackalytics',
        command     => 'pip install -r requirements.txt; python setup.py install',
        cwd         => $install_dir,
        path        => $::path,
        require     => [Package['python'],
                        Package['python-devel'],
                        Exec['Install pip'],
                        Exec['Install Development Tools']
        ]
    }

    user { $user:
        ensure  => present,
        managehome  => true,
        shell   => '/bin/sh',
        require => Exec['Install uwsgi']
    }

    file { $log_dir:
        ensure  => directory,
        owner   => $user,
        group   => $group,
        mode    => '0775',
        require => User[$user]
    }

    file { $log_file:
        ensure  => present,
        path    => "${log_dir}/${log_file}",
        owner   => $user,
        group   => $group,
        require => [Exec['Install uwsgi'], User[$user]]
    }

    file { $sources_root:
        ensure  => directory,
        owner   => $user,
        group   => $group,
        mode    => '0775',
        require => User[$user]
    }

    file { 'uwsgi':
        ensure  => present,
        path    => '/etc/init.d/uwsgi',
        content => template('spectrometer/uwsgi-init.sh.erb'),
        owner   => root,
        group   => root,
        mode    => '0755',
        require => [Exec['Install uwsgi'], User[$user]]
    }

    file { $config_dir:
        ensure  => directory,
        owner   => $user,
        group   => $group,
    }

    file { $config_file:
        ensure  => present,
        path    => "${config_dir}/${config_file}",
        content => template('spectrometer/spectrometer.conf.erb'),
        owner   => $user,
        group   => $group,
        require => [User[$user], File[$config_dir]]
    }

    file { $uwsgi_config_file:
        ensure  =>  present,
        path    =>  "${config_dir}/${uwsgi_config_file}",
        content =>  template('spectrometer/uwsgi.ini.erb'),
        owner   =>  $user,
        group   =>  $group,
        mode    => '0755',
        require => [User[$user],
                    File[$config_dir]
        ]
    }

    file { 'nginx.conf':
        ensure  => present,
        path    => '/etc/nginx/conf.d/stackalytics.conf',
        content => template('spectrometer/nginx.conf.erb'),
        owner   => nginx,
        group   => nginx,
        require => Package['nginx']
    }

    file { '/etc/nginx/conf.d/default.conf':
        ensure  => absent,
        require => Package['nginx'],
        before  => Service['nginx']
    }

    file { 'memcached':
        ensure  => present,
        path    => '/etc/sysconfig/memcached',
        content => template('spectrometer/memcached.erb'),
        owner   => root,
        group   => root,
        require => Package['memcached']
    }

    service { 'nginx':
        ensure  => running,
        enable  => true,
        require => [Service['uwsgi'],
                    File['nginx.conf']
        ]
    }

    service { 'memcached':
        ensure  => running,
        enable  => true,
        require => [Package['memcached'], File['memcached']]
    }

    service { 'uwsgi':
        ensure  => running,
        enable  => true,
        require => [File['uwsgi'],
                    File[$config_file],
                    File[$log_file],
                    Exec['Install uwsgi'],
                    User[$user],
                    Exec['Install Spectrometer'],
                    Service['memcached']
        ]
    }

    cron { 'stackalytics-processor':
        command     => "stackalytics-processor --log-file ${log_dir}/${processor_log_file} --config-file ${config_dir}/${config_file}",
        user        => $user,
        hour        => $processor_hour,
        minute      => $processor_minute,
        environment => "STACKALYTICS_CONF=${config_dir}/${config_file}",
        require     => Exec['Install Spectrometer']
    }

}

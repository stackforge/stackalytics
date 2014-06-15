# Spectrometer
class spectrometer (
    $clone_repo                 = 'UNSET',
    $git_repo_uri               = 'UNSET',
    $user                       = 'UNSET',
    $group                      = 'UNSET',
    $config_dir                 = 'UNSET',
    $config_file                = 'UNSET',
    $uwsgi_config_file          = 'UNSET',
    $log_dir                    = 'UNSET',
    $log_file                   = 'UNSET',
    $install_dir                = 'UNSET',
    $sources_root               = 'UNSET',
    $processor_hour             = 'UNSET',
    $processor_minute           = 'UNSET',
    $processor_log_file         = 'UNSET',
    $ssh_username               = 'UNSET',
    $ssh_key_filename           = 'UNSET',
    $uwsgi_port                 = 'UNSET',
    $uwsgi_pid_file             = 'UNSET',
    $default_data_uri           = 'UNSET',
    $runtime_storage_uri        = 'UNSET',
    $listen_host                = 'UNSET',
    $listen_port                = 'UNSET',
    $corrections_uri            = 'UNSET',
    $review_uri                 = 'UNSET',
    $force_update               = 'UNSET',
    $programs_uri               = 'UNSET',
    $default_metric             = 'UNSET',
    $default_release            = 'UNSET',
    $default_project_type       = 'UNSET',
    $dashboard_update_interval  = 'UNSET'
) {

    include spectrometer::params

    $_clone_repo = $clone_repo ? {
        'UNSET' => $::spectrometer::params::clone_repo,
        default => $clone_repo
    }

    $_git_repo_uri = $git_repo_uri ? {
        'UNSET' => $::spectrometer::params::git_repo_uri,
        default => $git_repo_uri
    }

    $_user = $user ? {
        'UNSET' => $::spectrometer::params::user,
        default => $user
    }

    $_group = $group ? {
        'UNSET' => $::spectrometer::params::group,
        default => $group
    }

    $_config_dir = $config_dir ? {
        'UNSET' => $::spectrometer::params::config_dir,
        default => $config_dir
    }

    $_config_file = $config_file ? {
        'UNSET' => $::spectrometer::params::config_file,
        default => $config_file
    }

    $_uwsgi_config_file = $uwsgi_config_file ? {
        'UNSET' => $::spectrometer::params::uwsgi_config_file,
        default => $uwsgi_config_file
    }

    $_log_dir = $log_dir ? {
        'UNSET' => $::spectrometer::params::log_dir,
        default => $log_dir
    }

    $_log_file = $log_file ? {
        'UNSET' => $::spectrometer::params::log_file,
        default => $log_file
    }

    $_install_dir = $install_dir ? {
        'UNSET' => $::spectrometer::params::install_dir,
        default => $install_dir
    }

    $_sources_root = $sources_root ? {
        'UNSET' => $::spectrometer::params::sources_root,
        default => $sources_root
    }

    $_processor_hour = $processor_hour ? {
        'UNSET' => $::spectrometer::params::processor_hour,
        default => $processor_hour
    }

    $_processor_minute = $processor_minute ? {
        'UNSET' => $::spectrometer::params::processor_minute,
        default => $processor_minute
    }

    $_processor_log_file = $processor_log_file ? {
        'UNSET' => $::spectrometer::params::processor_log_file,
        default => $processor_log_file
    }

    $_ssh_username = $ssh_username ? {
        'UNSET' => $::spectrometer::params::ssh_username,
        default => $ssh_username
    }

    $_ssh_key_filename = $ssh_key_filename ? {
        'UNSET' => $::spectrometer::params::ssh_key_filename,
        default => $ssh_key_filename
    }

    $_uwsgi_port = $uwsgi_port ? {
        'UNSET' => $::spectrometer::params::uwsgi_port,
        default => $uwsgi_port
    }

    $_uwsgi_pid_file = $uwsgi_pid_file ? {
        'UNSET' => $::spectrometer::params::uwsgi_pid_file,
        default => $uwsgi_pid_file
    }

    $_default_data_uri = $default_data_uri ? {
        'UNSET' => $::spectrometer::params::default_data_uri,
        default => $default_data_uri
    }

    $_runtime_storage_uri = $runtime_storage_uri ? {
        'UNSET' => $::spectrometer::params::runtime_storage_uri,
        default => $runtime_storage_uri
    }

    $_listen_host = $listen_host ? {
        'UNSET' => $::spectrometer::params::listen_host,
        default => $listen_host
    }

    $_listen_port = $listen_port ? {
        'UNSET' => $::spectrometer::params::listen_port,
        default => $listen_port
    }

    $_corrections_uri = $corrections_uri ? {
        'UNSET' => $::spectrometer::params::corrections_uri,
        default => $corrections_uri
    }

    $_review_uri = $review_uri ? {
        'UNSET' => $::spectrometer::params::review_uri,
        default => $review_uri
    }

    $_force_update = $force_update ? {
        'UNSET' => $::spectrometer::params::force_update,
        default => $force_update
    }

    $_programs_uri = $programs_uri ? {
        'UNSET' => $::spectrometer::params::programs_uri,
        default => $programs_uri
    }

    $_default_metric = $default_metric ? {
        'UNSET' => $::spectrometer::params::default_metric,
        default => $default_metric
    }

    $_default_release = $default_release ? {
        'UNSET' => $::spectrometer::params::default_release,
        default => $default_release
    }

    $_default_project_type = $default_project_type ? {
        'UNSET' => $::spectrometer::params::default_project_type,
        default => $default_project_type
    }

    $_dashboard_update_interval = $dashboard_update_interval ? {
        'UNSET' => $::spectrometer::params::dashboard_update_interval,
        default => $dashboard_update_interval
    }

    class {'epel':}

    if $_clone_repo == true {
        vcsrepo { $_install_dir:
            ensure   => present,
            provider => git,
            source   => $_git_repo_uri,
        }
    }

    exec { 'Install Development Tools':
      unless  => 'yum grouplist "Development tools" | grep "^Installed Groups"',
      command => 'yum -y groupinstall "Development tools"',
      path    => $::path
    }

    $deps = [ 'openldap-devel',
              'python',
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
        cwd         => $_install_dir,
        path        => $::path,
        require     => [Package['openldap-devel'],
                        Package['python'],
                        Package['python-devel'],
                        Exec['Install pip'],
                        Exec['Install Development Tools']
        ]
    }

    user { $_user:
        ensure      => present,
        managehome  => true,
        shell       => '/bin/sh',
        require     => Exec['Install uwsgi']
    }

    file { $_log_dir:
        ensure  => directory,
        owner   => $_user,
        group   => $_group,
        mode    => '0775',
        require => User[$_user]
    }

    file { $_log_file:
        ensure  => present,
        path    => "${_log_dir}/${_log_file}",
        owner   => $_user,
        group   => $_group,
        require => [Exec['Install uwsgi'], User[$_user]]
    }

    file { $_sources_root:
        ensure  => directory,
        owner   => $_user,
        group   => $_group,
        mode    => '0775',
        require => User[$_user]
    }

    file { 'uwsgi':
        ensure  => present,
        path    => '/etc/init.d/uwsgi',
        content => template('spectrometer/uwsgi-init.sh.erb'),
        owner   => root,
        group   => root,
        mode    => '0755',
        require => [Exec['Install uwsgi'], User[$_user]]
    }

    file { $_config_dir:
        ensure  => directory,
        owner   => $_user,
        group   => $_group,
    }

    file { $_config_file:
        ensure  => present,
        path    => "${_config_dir}/${_config_file}",
        content => template('spectrometer/spectrometer.conf.erb'),
        owner   => $_user,
        group   => $_group,
        require => [User[$_user], File[$_config_dir]]
    }

    file { $_uwsgi_config_file:
        ensure  =>  present,
        path    =>  "${_config_dir}/${_uwsgi_config_file}",
        content =>  template('spectrometer/uwsgi.ini.erb'),
        owner   =>  $_user,
        group   =>  $_group,
        mode    => '0755',
        require => [User[$_user],
                    File[$_config_dir]
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
                    File[$_config_file],
                    File[$_log_file],
                    Exec['Install uwsgi'],
                    User[$_user],
                    Exec['Install Spectrometer'],
                    Service['memcached']
        ]
    }

    cron { 'stackalytics-processor':
        command     => "stackalytics-processor --log-file ${_log_dir}/${_processor_log_file} --config-file ${_config_dir}/${_config_file}",
        user        => $_user,
        hour        => $_processor_hour,
        minute      => $_processor_minute,
        environment => "STACKALYTICS_CONF=${_config_dir}/${_config_file}",
        require     => Exec['Install Spectrometer']
    }

}

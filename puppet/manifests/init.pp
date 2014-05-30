exec { "Install EPEL":
     command => "wget http://download.fedoraproject.org/pub/epel/6/x86_64/epel-release-6-8.noarch.rpm; rpm -ivh epel-release-6-8.noarch.rpm",
     user => root,
     path => $path,
     cwd => "/tmp",
     unless => "rpm -q epel-release",
     notify => Exec["Update Yum"]
}

exec { "Update Yum":
     command => "yum -q -y update",
     path => $path
}

exec { 'Install Development Tools':
  unless  => '/usr/bin/yum grouplist "Development tools" | /bin/grep "^Installed Groups"',
  command => '/usr/bin/yum -y groupinstall "Development tools"',
}

$deps = [ "python",
          "python-devel",
          "python-setuptools",
          "git"
]

package { $deps:
    ensure => "installed"
}

file { "uwsgi-2.0.4-1.x86_64.rpm":
     ensure => present,
     path => "/tmp/uwsgi-2.0.4-1.x86_64.rpm",
     source => "puppet:///files/uwsgi-2.0.4-1.x86_64.rpm",
     owner => root,
     group => root
}

package { "memcached":
     ensure => installed,
     require => Exec["Install EPEL"]
}

package { "nginx":
     ensure => installed,
     require => Exec["Install EPEL"]
}

package { "uwsgi":
     ensure => installed,
     provider => rpm,
     source => "/tmp/uwsgi-2.0.4-1.x86_64.rpm",
     require => File["uwsgi-2.0.4-1.x86_64.rpm"]
}

user { "stackalytics":
        ensure => present,
        groups => ['vagrant'],
        home => "/opt/uwsgi",
        shell => "/bin/sh",
        require => Package["uwsgi"]
}

file { "/var/local/stackalytics":
     ensure => present,
     owner => stackalytics,
     group => stackalytics,
     require => User["stackalytics"]
}

file { "/opt/uwsgi":
     ensure => directory,
     owner => stackalytics,
     group => stackalytics,
     require => [Package["uwsgi"], User["stackalytics"]]
}

file { "uwsgi.log":
     path => "/var/log/uwsgi.log",
     ensure => present,
     owner => stackalytics,
     group => stackalytics,
     require => [Package["uwsgi"], User["stackalytics"]]
}

file { "uwsgi":
     path => "/etc/init.d/uwsgi",
     ensure => present,
     content => template("uwsgi-init.sh.erb"),
     owner => root,
     group => root,
     mode => 755,
     require => [Package["uwsgi"], User["stackalytics"]]
}

file { "uwsgi.ini":
     path => "/opt/uwsgi/uwsgi.ini",
     ensure => present,
     content => template("uwsgi.ini.erb"),
     owner => stackalytics,
     group => stackalytics,
     mode => 755,
     require => [Package["uwsgi"], User["stackalytics"]]
}

file { "stackalytics.conf":
     path => "/etc/nginx/conf.d/stackalytics.conf",
     ensure => present,
     content => template("stackalytics.conf.erb"),
     owner => nginx,
     group => nginx,
     require => Package["nginx"]
}

file { "/etc/nginx/conf.d/default.conf":
     ensure => absent,
     require => Package["nginx"]
}

file { "memcached":
     ensure => present,
     path => "/etc/sysconfig/memcached",
     content => template("memcached.erb"),
     owner => root,
     group => root,
     require => Package["memcached"]
}

service { "uwsgi":
     enable => true,
     ensure => running,
     require => [File["uwsgi"],
                 File["uwsgi.ini"],
                 File["uwsgi.log"],
                 Package["uwsgi"],
                 User["stackalytics"],
                 Exec["Install Stackalytics"]
     ]
}

service { "nginx":
     enable => true,
     ensure => running,
     require => [Service["uwsgi"],
                 File["stackalytics.conf"]
     ]
}

service { "memcached":
     enable => true,
     ensure => running,
     require => [Package["memcached"], File["memcached"]]
}

exec { "Install pip":
     unless => "which pip",
     command => "easy_install pip",
     path => $path,
     user => root,
     require => Package["python-setuptools"]
}

exec { "Install Stackalytics":
     unless => "pip list | grep stackalytics",
     command => "pip install -r requirements.txt; python setup.py install",
     cwd => "/opt/stack/stackalytics",
     path => $path,
     require =>[Package["python"],
                Package["python-devel"],
                Exec["Install pip"],
                Exec["Install Development Tools"]
     ]
}

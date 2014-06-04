class {'spectrometer':
    clone_repo          => false,
    processor_hour      => '*',
    processor_minute    => '*/20',
    gerrit_username     => dave-tucker
}

file {'ssh':
    ensure  => directory,
    path    => '/home/spectrometer/.ssh/',
    owner   => 'spectrometer',
    group   => 'spectrometer'
}

file {'priv':
    ensure  => present,
    source  => 'puppet:///files/spectrometer',
    path    => '/home/spectrometer/.ssh/id_rsa',
    owner   => 'spectrometer',
    group   => 'spectrometer',
    require => File['ssh']
}

file {'pub':
    ensure  => present,
    source  => 'puppet:///files/spectrometer.pub',
    path    => '/home/spectrometer/.ssh/id_rsa.pub',
    owner   => 'spectrometer',
    group   => 'spectrometer',
    require => File['ssh']
}

class {'spectrometer':
    clone_repo          => false,
    processor_hour      => '*',
    processor_minute    => '*/20',
    ssh_username        => dave-tucker
}

file {'ssh':
    ensure  => directory,
    path    => '/home/spectrometer/.ssh/',
    owner   => 'spectrometer',
    group   => 'spectrometer'
}

file {'priv':
    ensure  => present,
    source  => 'puppet:///files/spectrometer_rsa',
    path    => '/home/spectrometer/.ssh/id_rsa',
    owner   => 'spectrometer',
    group   => 'spectrometer',
    require => File['ssh']
}

file {'pub':
    ensure  => present,
    source  => 'puppet:///files/spectrometer_rsa.pub',
    path    => '/home/spectrometer/.ssh/id_rsa.pub',
    owner   => 'spectrometer',
    group   => 'spectrometer',
    require => File['ssh']
}

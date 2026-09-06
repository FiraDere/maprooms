from app.dst_api.scripts.spei_compute import get_spi_distribution_pars

def main():
    params = {
        'dataset': 'MON',
        'variable': 'precip',
        'analysis': 'spi',
        'distribution': 'gamma',
    }
    pars_dek = params.copy()
    pars_dek['temporalRes'] = 'dekadal'
    pars_dek['timeScale'] = 1
    tmp = get_spi_distribution_pars(pars_dek)

    pars_mon = params.copy()
    pars_mon['temporalRes'] = 'monthly'
    pars_mon['timeScale'] = 1
    tmp = get_spi_distribution_pars(pars_mon)

    pars_seas = params.copy()
    pars_seas['temporalRes'] = 'seasonal'
    pars_seas['timeScale'] = 3
    pars_seas['timeRes'] = 'monthly'
    tmp = get_spi_distribution_pars(pars_seas)

if __name__ == '__main__':
    main()

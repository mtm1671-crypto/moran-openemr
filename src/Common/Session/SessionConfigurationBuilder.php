<?php

/*
 * SessionConfigurationBuilder.php
 * @package openemr
 * @link      https://www.open-emr.org
 * @license   https://github.com/openemr/openemr/blob/master/LICENSE GNU General Public License 3
 */

namespace OpenEMR\Common\Session;

class SessionConfigurationBuilder
{
    /** @var array<string, mixed> */
    private array $config = [];

    public function __construct()
    {
        // Set default values that are common across all session types
        $this->config = [
            'gc_maxlifetime' => SessionUtil::DEFAULT_GC_MAXLIFETIME,
            'use_strict_mode' => true,
            'use_cookies' => true,
            'use_only_cookies' => true,
            'cookie_samesite' => 'Strict',
            'cookie_secure' => self::forceSecureCookieAttributes(),
            'cookie_httponly' => true
        ];

        // Add PHP version-specific settings
        if (version_compare(phpversion(), '8.4.0', '<')) {
            $this->config['sid_bits_per_character'] = 6;
            $this->config['sid_length'] = 48;
        }
    }

    public function setName(string $name): self
    {
        $this->config['name'] = $name;
        return $this;
    }

    public function setCookiePath(string $path): self
    {
        $this->config['cookie_path'] = $path;
        return $this;
    }

    public function setCookieSameSite(string $sameSite): self
    {
        $this->config['cookie_samesite'] = $sameSite;
        return $this;
    }

    public function setCookieSecure(bool $secure): self
    {
        $this->config['cookie_secure'] = $secure;
        return $this;
    }

    public function setCookieHttpOnly(bool $httpOnly): self
    {
        $this->config['cookie_httponly'] = $httpOnly;
        return $this;
    }

    public function setReadOnly(bool $readOnly): self
    {
        $this->config['read_and_close'] = $readOnly;
        return $this;
    }

    /**
     * @return array<string, mixed>
     */
    public function build(): array
    {
        return $this->config;
    }

    public static function forceSecureCookieAttributes(): bool
    {
        $value = getenv('AGENTFORGE_SECURE_COOKIES');
        return is_string($value) && in_array(strtolower($value), ['1', 'true', 'yes', 'on'], true);
    }

    // Preset configurations for different session types
    /** @return array<string, mixed> */
    public static function forCore(string $webRoot = '', bool $readOnly = true): array
    {
        $builder = (new self())
            ->setName(SessionUtil::CORE_SESSION_ID)
            ->setCookiePath((!empty($webRoot)) ? $webRoot . '/' : '/')
            ->setReadOnly($readOnly);
        if (!self::forceSecureCookieAttributes()) {
            $builder->setCookieHttpOnly(false);
        }
        return $builder->build();
    }

    /** @return array<string, mixed> */
    public static function forOAuth(string $webRoot = ''): array
    {
        return (new self())
            ->setName(SessionUtil::OAUTH_SESSION_ID)
            ->setCookiePath((!empty($webRoot)) ? $webRoot . SessionUtil::OAUTH_WEBROOT : SessionUtil::OAUTH_WEBROOT)
            ->setCookieSameSite('None')
            ->setCookieSecure(true)
            ->build();
    }

    /** @return array<string, mixed> */
    public static function forApi(string $webRoot = ''): array
    {
        return (new self())
            ->setName(SessionUtil::API_SESSION_ID)
            ->setCookiePath((!empty($webRoot)) ? $webRoot . SessionUtil::API_WEBROOT : SessionUtil::API_WEBROOT)
            ->setCookieSecure(true)
            ->build();
    }

    /** @return array<string, mixed> */
    public static function forPortal(string $webRoot = '', bool $readOnly = true): array
    {
        return (new self())
            ->setName(SessionUtil::PORTAL_SESSION_ID)
            ->setCookiePath($webRoot !== '' ? $webRoot . '/' : '/')
            ->setReadOnly($readOnly)
            ->build();
    }

    /** @return array<string, mixed> */
    public static function forSetup(): array
    {
        return (new self())
            ->setName(SessionUtil::SETUP_SESSION_ID)
            ->build();
    }
}
